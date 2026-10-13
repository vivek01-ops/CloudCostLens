import {
  Activity,
  BarChart3,
  CheckSquare,
  Gauge,
  Layers,
  Settings,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

export const NAV_ITEMS: NavItem[] = [
  { label: "Overview", href: "/overview", icon: Gauge },
  { label: "Resources", href: "/resources", icon: Layers },
  { label: "Cost Explorer", href: "/cost-explorer", icon: BarChart3 },
  { label: "Recommendations", href: "/recommendations", icon: CheckSquare },
  { label: "Approval Center", href: "/approvals", icon: ShieldCheck },
  { label: "Activity & Audit", href: "/activity", icon: Activity },
  { label: "Settings", href: "/settings", icon: Settings },
];

export const BRAND = "CloudCostLens";