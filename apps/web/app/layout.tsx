import "./globals.css";
export const metadata = { title: "Atlas Intelligence", description: "Autonomous enterprise research platform" };
export default function Root({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body>{children}</body></html>;
}
