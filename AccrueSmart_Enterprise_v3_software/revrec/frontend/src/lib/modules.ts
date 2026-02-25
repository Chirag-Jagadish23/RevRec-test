export type AppModule = {
  key: string;
  label: string;
  href: string;
  enabled: boolean;
  description?: string;
};

export const APP_MODULES: AppModule[] = [
  {
    key: "catalog",
    label: "Catalog",
    href: "/catalog",
    enabled: true,
    description: "Products and rev rec rules",
  },
  {
    key: "contracts",
    label: "Contracts",
    href: "/contracts",
    enabled: true,
    description: "Contract setup and line items",
  },
  {
    key: "schedules",
    label: "Schedules",
    href: "/schedules/editor",
    enabled: true,
    description: "Revenue schedule editor",
  },
  {
    key: "viewer",
    label: "Viewer",
    href: "/viewer",
    enabled: true,
    description: "Schedule viewer",
  },
  {
    key: "reports",
    label: "Reports",
    href: "/reports",
    enabled: true,
    description: "Lock schedules and reporting",
  },
  {
    key: "costs",
    label: "ASC 340 Costs",
    href: "/costs",
    enabled: true,
    description: "Cost capitalization amortization",
  },
  {
    key: "leases",
    label: "ASC 842 Leases",
    href: "/leases",
    enabled: true,
    description: "Lease schedule and journals",
  },
  {
    key: "tax",
    label: "ASC 740 Tax",
    href: "/tax",
    enabled: true,
    description: "Deferred tax + memo + ETR bridge",
  },

  // Keep future modules here but disabled so they do not break the UI:
  // {
  //   key: "stock-comp",
  //   label: "ASC 718 Stock Comp",
  //   href: "/stock-comp",
  //   enabled: false,
  //   description: "Coming soon",
  // },
];
