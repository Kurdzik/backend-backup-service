"use client";

import { Box, Stack, Text, ScrollArea, Tooltip } from "@mantine/core";
import {
  IconDatabase,
  IconCloud,
  IconLogout,
  IconAugmentedReality,
  IconCalendarTime,
  IconUser,
  IconApps,
  IconChevronLeft,
  IconChevronRight,
} from "@tabler/icons-react";
import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import classes from "@/components/Sidebar.module.css";
import { removeAuthCookie } from "@/lib/cookies";

interface NavItem {
  icon: React.ReactNode;
  label: string;
  route?: string;
}

const mainItems: NavItem[] = [
  { icon: <IconApps size={16} stroke={1.5} />, label: "Connected Applications", route: "/ui/connected_apps" },
  { icon: <IconCloud size={16} stroke={1.5} />, label: "Backup Destinations", route: "/ui/backup_destinations" },
  { icon: <IconCalendarTime size={16} stroke={1.5} />, label: "Backup Schedules", route: "/ui/backup_schedules" },
  { icon: <IconDatabase size={16} stroke={1.5} />, label: "Manage Backups", route: "/ui/backups" },
];

const bottomItems: NavItem[] = [
  { icon: <IconUser size={16} stroke={1.5} />, label: "User Information", route: "/ui/user_info" },
  { icon: <IconLogout size={16} stroke={1.5} />, label: "Logout" },
];

interface SidebarItemProps {
  item: NavItem;
  active: boolean;
  collapsed: boolean;
  onClick?: () => void;
}

const SidebarItem = ({ item, active, collapsed, onClick }: SidebarItemProps) => {
  const inner = (
    <button
      className={classes.navItem}
      data-active={active || undefined}
      onClick={onClick}
    >
      <span className={classes.navItemIcon}>{item.icon}</span>
      {!collapsed && <span className={classes.navItemLabel}>{item.label}</span>}
    </button>
  );

  const wrapped = collapsed ? (
    <Tooltip label={item.label} position="right" offset={8}>
      {inner}
    </Tooltip>
  ) : inner;

  if (item.route) {
    return (
      <Link href={item.route} style={{ textDecoration: "none", display: "block" }}>
        {wrapped}
      </Link>
    );
  }

  return wrapped;
};

export const SidebarComponent = () => {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = React.useState(false);

  React.useEffect(() => {
    const saved = localStorage.getItem("sidebar-collapsed");
    if (saved) setCollapsed(JSON.parse(saved));
  }, []);

  const toggleCollapsed = () => {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem("sidebar-collapsed", JSON.stringify(next));
  };

  const handleLogout = async () => {
    try {
      await removeAuthCookie();
      window.location.href = "/";
    } catch (e) {
      console.error("Logout error:", e);
    }
  };

  return (
    <Box
      className={classes.sidebarContainer}
      data-collapsed={collapsed || undefined}
      style={{ transition: "width 150ms ease" }}
    >
      {/* Header */}
      <Box className={classes.sidebarHeader}>
        <Box className={classes.appIcon}>
          <IconAugmentedReality size={12} stroke={2} />
        </Box>
        {!collapsed && <Text className={classes.appTitle}>Backup Manager</Text>}
        <Tooltip label={collapsed ? "Expand sidebar" : "Collapse sidebar"} position="right" offset={8}>
          <button
            onClick={toggleCollapsed}
            className={classes.headerAction}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed
              ? <IconChevronRight size={14} stroke={1.8} />
              : <IconChevronLeft size={14} stroke={1.8} />}
          </button>
        </Tooltip>
      </Box>

      {/* Main nav */}
      <ScrollArea className={classes.scrollArea}>
        <Stack gap={2}>
          {!collapsed && <Text className={classes.sectionLabel}>Management</Text>}
          {mainItems.map((item) => (
            <SidebarItem
              key={item.label}
              item={item}
              active={!!item.route && pathname.startsWith(item.route)}
              collapsed={collapsed}
            />
          ))}
        </Stack>
      </ScrollArea>

      {/* Bottom */}
      <Box className={classes.sidebarBottom}>
        <Stack gap={2}>
          {!collapsed && <Text className={classes.sectionLabel} style={{ marginTop: 0 }}>Account</Text>}
          {bottomItems.map((item) => (
            <SidebarItem
              key={item.label}
              item={item}
              active={!!item.route && pathname.startsWith(item.route)}
              collapsed={collapsed}
              onClick={item.label === "Logout" ? handleLogout : undefined}
            />
          ))}
        </Stack>
      </Box>
    </Box>
  );
};
