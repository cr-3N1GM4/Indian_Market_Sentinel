import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "IMS — Indian Market Sentinel",
  description: "Regime-Conditioned Market Intelligence Terminal",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="bg-ims-bg text-ims-text-primary font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
