"use client";

import {
  Box,
  Stack,
  Text,
  ScrollArea,
  Group,
  ThemeIcon,
  UnstyledButton,
  Divider,
  ActionIcon,
  Tooltip,
} from "@mantine/core";
import {
  IconDatabase,
  IconCloud,
  IconLogout,
  IconAugmentedReality,
  IconCalendarTime,
  IconChevronLeft,
  IconChevronRight,
  IconUser,
  IconApps,
} from "@tabler/icons-react";
import React from "react";
import Link from "next/link";
import classes from "@/components/Sidebar.module.css";
import { removeAuthCookie } from "@/lib/cookies";

interface SidebarItemProps {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  onClick?: () => void;
  href?: string;
  badge?: string | number;
  status?: "online" | "warning" | "error" | "offline";
  collapsed?: boolean;
}

interface MainItemType {
  icon: React.ReactNode;
  label: string;
  route: string;
  badge?: string | number;
  status?: "online" | "warning" | "error" | "offline";
}

const mainItems: MainItemType[] = [
  {
    icon: <IconApps size={16} stroke={1.5} />,
    label: "Connected Applications",
    route: "/ui/connected_apps",
  },
  {
    icon: <IconCloud size={16} stroke={1.5} />,
    label: "Backup Destinations",
    route: "/ui/backup_destinations",
  },
  {
    icon: <IconCalendarTime size={16} stroke={1.5} />,
    label: "Backup Schedules",
    route: "/ui/backup_schedules",
  },
  {
    icon: <IconDatabase size={16} stroke={1.5} />,
    label: "Manage Backups",
    route: "/ui/backups",
  },
];

const bottomItems = [
  {
    icon: <IconUser size={16} stroke={1.5} />,
    label: "User Information",
    route: "/ui/user_info",
  },
  {
    icon: <IconLogout size={16} stroke={1.5} />,
    label: "Logout",
  },
];

const StatusDot = ({
  status,
}: {
  status?: "online" | "warning" | "error" | "offline";
}) => {
  if (!status) return null;

  return <Box className={`${classes.statusDot} ${classes[status]}`} />;
};

const ItemBadge = ({ badge }: { badge?: string | number }) => {
  if (!badge) return null;

  return (
    <Text size="xs" fw={500} className={classes.itemBadge}>
      {badge}
    </Text>
  );
};

const SidebarItem = ({
  icon,
  label,
  active = false,
  onClick,
  href,
  badge,
  status,
  collapsed = false,
}: SidebarItemProps) => {
  const buttonContent = (
    <UnstyledButton
      onClick={onClick}
      data-active={active || undefined}
      className={classes.sidebarItem}
    >
      <ThemeIcon
        variant="light"
        size={28}
        radius={0}
        className={classes.itemIcon}
        color={active ? "slate" : "gray"}
      >
        {icon}
      </ThemeIcon>

      {!collapsed && (
        <>
          <Text
            size="sm"
            fw={active ? 500 : 400}
            className={classes.itemText}
          >
            {label}
          </Text>

          <Group gap={6} align="center" wrap="nowrap">
            <ItemBadge badge={badge} />
            <StatusDot status={status} />
          </Group>
        </>
      )}
    </UnstyledButton>
  );

  const content = collapsed ? (
    <Tooltip label={label} position="right" withArrow offset={8}>
      {buttonContent}
    </Tooltip>
  ) : (
    buttonContent
  );

  if (href) {
    return (
      <Link href={href} style={{ textDecoration: "none", color: "inherit" }}>
        {content}
      </Link>
    );
  }

  return content;
};

export const SidebarComponent = () => {
  const [activeItem, setActiveItem] = React.useState("Connected Applications");
  const [collapsed, setCollapsed] = React.useState(false);

  React.useEffect(() => {
    if (typeof window !== "undefined") {
      const savedActiveItem = localStorage.getItem("sidebar-active-item");
      const savedCollapsed = localStorage.getItem("sidebar-collapsed");

      if (savedActiveItem) {
        setActiveItem(savedActiveItem);
      }

      if (savedCollapsed) {
        setCollapsed(JSON.parse(savedCollapsed));
      }
    }
  }, []);

  const handleItemClick = (label: string) => {
    setActiveItem(label);
    if (typeof window !== "undefined") {
      localStorage.setItem("sidebar-active-item", label);
    }
  };

  const handleLogout = async () => {
    try {
      await removeAuthCookie();
      window.location.href = "/";
    } catch (error) {
      console.error("Error during logout:", error);
    }
  };

  const toggleCollapsed = () => {
    const newCollapsed = !collapsed;
    setCollapsed(newCollapsed);
    if (typeof window !== "undefined") {
      localStorage.setItem("sidebar-collapsed", JSON.stringify(newCollapsed));
    }
  };

  return (
    <Box
      className={classes.sidebarContainer}
      style={{
        width: collapsed ? "80px" : "280px",
        transition: "width 150ms cubic-bezier(0.4, 0, 0.2, 1)",
      }}
    >
      {/* Header */}
      <Box className={classes.sidebarHeader}>
        <Group gap="sm" align="center" justify="space-between">
          {!collapsed && (
            <Group gap={10} align="center">
              <ThemeIcon
                size={28}
                radius={0}
                variant="light"
                color="slate"
              >
                <IconAugmentedReality size={16} stroke={2} />
              </ThemeIcon>
              <Text fw={600} size="sm" className={classes.appTitle}>
                Backup Manager
              </Text>
            </Group>
          )}
          {collapsed && (
            <ThemeIcon
              size={28}
              radius={0}
              variant="light"
              color="slate"
            >
              <IconAugmentedReality size={16} stroke={2} />
            </ThemeIcon>
          )}
        </Group>
      </Box>

      <Divider className={classes.headerDivider} />

      {/* Collapse Toggle */}
      <Box p="8px">
        <Group justify={collapsed ? "center" : "flex-end"}>
          <ActionIcon
            variant="subtle"
            size="sm"
            onClick={toggleCollapsed}
            className={classes.collapseButton}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? (
              <IconChevronRight size={16} stroke={2} />
            ) : (
              <IconChevronLeft size={16} stroke={2} />
            )}
          </ActionIcon>
        </Group>
      </Box>

      {/* Main Navigation */}
      <ScrollArea flex={1} p="12px" className={classes.scrollArea}>
        <Stack gap={8}>
          <Box className={classes.menuSection}>
            {!collapsed && (
              <Text
                size="xs"
                fw={500}
                c="dimmed"
                tt="uppercase"
                mb={8}
                className={classes.sectionLabel}
              >
                Management
              </Text>
            )}

            <Stack gap={2}>
              {mainItems.map((item) => (
                <SidebarItem
                  key={item.label}
                  icon={item.icon}
                  label={item.label}
                  active={activeItem === item.label}
                  href={item.route}
                  badge={item.badge}
                  status={item.status}
                  collapsed={collapsed}
                  onClick={() => handleItemClick(item.label)}
                />
              ))}
            </Stack>
          </Box>
        </Stack>
      </ScrollArea>

      {/* Bottom Section */}
      <Box className={classes.sidebarBottom}>
        <Divider className={classes.bottomDivider} />

        <Box p="12px">
          {!collapsed && (
            <Text
              size="xs"
              fw={500}
              c="dimmed"
              tt="uppercase"
              mb={8}
              className={classes.sectionLabel}
            >
              Account
            </Text>
          )}

          <Stack gap={2}>
            {bottomItems.map((item) => (
              <SidebarItem
                key={item.label}
                icon={item.icon}
                label={item.label}
                active={activeItem === item.label}
                href={item.route}
                collapsed={collapsed}
                onClick={() => {
                  if (item.label === "Logout") {
                    handleLogout();
                  } else {
                    handleItemClick(item.label);
                  }
                }}
              />
            ))}
          </Stack>
        </Box>
      </Box>
    </Box>
  );
};