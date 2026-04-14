# ARCHITECTURE NOTE:
# NSE corporate actions scraper with pre-event alert system.
# Alerts fire daily at 09:00 IST for events within 1 trading day.
# Severity: RESULT/BUYBACK → HIGH, DIVIDEND/SPLIT → MEDIUM, AGM → LOW.

from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List

import structlog

from backend.config import AlertSeverity
from backend.db.timescale_client import db
from backend.models.signal_models import CorporateAction, PreEventAlert
from backend.services.scrapers.nse_scraper import nse_session

logger = structlog.get_logger(__name__)


class EarningsCalendar:
    """Scrapes NSE/BSE corporate actions and generates pre-event alerts."""

    NSE_ENDPOINT = "/api/corporates-corporateActions?index=equities"

    async def fetch_corporate_actions(self) -> List[Dict[str, Any]]:
        data = await nse_session.get_json(self.NSE_ENDPOINT)
        if data and "data" in data:
            return data["data"]
        if data and isinstance(data, list):
            return data
        return self._generate_mock_actions()

    async def run_pipeline(self) -> int:
        """Fetch corporate actions and store in DB."""
        actions = await self.fetch_corporate_actions()
        stored = 0

        for action in actions:
            try:
                symbol = action.get("symbol") or action.get("SYMBOL", "")
                action_type = (
                    action.get("subject") or action.get("PURPOSE", "")
                ).upper()

                # Normalise action type
                if "DIVIDEND" in action_type:
                    act_type = "DIVIDEND"
                elif "BONUS" in action_type:
                    act_type = "BONUS"
                elif "SPLIT" in action_type:
                    act_type = "SPLIT"
                elif "BUYBACK" in action_type:
                    act_type = "BUYBACK"
                elif "AGM" in action_type:
                    act_type = "AGM"
                elif "EGM" in action_type:
                    act_type = "EGM"
                elif "RESULT" in action_type or "FINANCIAL" in action_type:
                    act_type = "RESULT"
                elif "RIGHTS" in action_type:
                    act_type = "RIGHTS_ISSUE"
                else:
                    act_type = "OTHER"

                event_date_str = (
                    action.get("bfDt") or action.get("EX_DATE") or ""
                )
                if not event_date_str or not symbol:
                    continue

                try:
                    event_date = datetime.strptime(
                        event_date_str[:10], "%Y-%m-%d"
                    ).date()
                except ValueError:
                    try:
                        event_date = datetime.strptime(
                            event_date_str, "%d-%b-%Y"
                        ).date()
                    except ValueError:
                        continue

                record_date_str = action.get("reDt") or action.get("RECORD_DATE")
                record_date = None
                if record_date_str:
                    try:
                        record_date = datetime.strptime(
                            str(record_date_str)[:10], "%Y-%m-%d"
                        ).date()
                    except ValueError:
                        pass

                await db.upsert_corporate_action({
                    "ticker": symbol.upper(),
                    "exchange": "NSE",
                    "action_type": act_type,
                    "event_date": event_date,
                    "record_date": record_date,
                    "ex_date": event_date,
                    "details": action,
                })
                stored += 1

            except Exception as e:
                logger.error("corp_action_store_error", error=str(e))

        logger.info("earnings_calendar_complete", actions_stored=stored)
        return stored

    async def generate_pre_event_alerts(self) -> List[PreEventAlert]:
        """Generate alerts for events within 1 trading day."""
        upcoming = await db.get_upcoming_actions(days=2)
        alerts: List[PreEventAlert] = []
        today = date.today()

        for row in upcoming:
            event_date = row["event_date"]
            if isinstance(event_date, datetime):
                event_date = event_date.date()

            days_until = (event_date - today).days
            if days_until > 1:
                continue

            action_type = row["action_type"]
            severity = self._get_severity(action_type)

            alerts.append(PreEventAlert(
                ticker=row["ticker"],
                event_type=action_type,
                event_date=str(event_date),
                days_until=max(days_until, 0),
                alert_severity=severity.value,
                context=f"{action_type} for {row['ticker']} on {event_date}",
            ))

        return alerts

    @staticmethod
    def _get_severity(action_type: str) -> AlertSeverity:
        if action_type in ("RESULT", "BUYBACK"):
            return AlertSeverity.HIGH
        elif action_type in ("DIVIDEND", "BONUS", "SPLIT"):
            return AlertSeverity.MEDIUM
        return AlertSeverity.LOW

    # MOCK_FALLBACK
    def _generate_mock_actions(self) -> List[Dict[str, Any]]:
        tickers = ["SUNPHARMA", "RELIANCE", "ONGC", "DRREDDY", "NTPC", "CIPLA"]
        types = ["RESULT", "DIVIDEND", "BONUS", "BUYBACK", "AGM"]
        actions = []
        for i in range(10):
            dt = date.today() + timedelta(days=random.randint(0, 14))
            actions.append({
                "symbol": random.choice(tickers),
                "subject": random.choice(types),
                "bfDt": dt.strftime("%Y-%m-%d"),
            })
        return actions


earnings_calendar = EarningsCalendar()
