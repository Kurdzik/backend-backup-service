"use client";
import { createTheme, rem } from "@mantine/core";

export const theme = createTheme({
  defaultRadius: 0, // Sharp corners - style
  cursorType: "pointer",

  primaryColor: "slate",
  primaryShade: { light: 6, dark: 5 },

  // inspired typography - Inter font family
  fontFamily: `"Segoe UI", "Inter", -apple-system, BlinkMacSystemFont, "Roboto", "Helvetica Neue", Arial, sans-serif`,

  fontSizes: {
    xs: rem(11),
    sm: rem(12),
    md: rem(13),
    lg: rem(14),
    xl: rem(16),
  },

  colors: {
    slate: [
      "#f8fafc",
      "#f1f5f9",
      "#e2e8f0",
      "#cbd5e1",
      "#94a3b8",
      "#64748b", // ⬅️ primary - modern slate
      "#475569",
      "#334155",
      "#1e293b",
      "#0f172a",
    ],
    neutral: [
      "#ffffff",
      "#f8fafc",
      "#f1f5f9",
      "#e2e8f0",
      "#cbd5e1",
      "#94a3b8",
      "#64748b",
      "#475569", // Subtle borders
      "#334155",
      "#1e293b",
    ],
    success: [
      "#f0fdf4",
      "#dcfce7",
      "#bbf7d0",
      "#86efac",
      "#4ade80",
      "#22c55e", // ⬅️ clean green but muted
      "#16a34a",
      "#15803d",
      "#166534",
      "#14532d",
    ],
    warning: [
      "#fffbeb",
      "#fef3c7",
      "#fde68a",
      "#fcd34d",
      "#fbbf24",
      "#f59e0b", // ⬅️ clean amber
      "#d97706",
      "#b45309",
      "#92400e",
      "#78350f",
    ],
    error: [
      "#fef2f2",
      "#fecaca",
      "#fca5a5",
      "#f87171",
      "#ef4444",
      "#dc2626", // ⬅️ clean red but restrained
      "#b91c1c",
      "#991b1b",
      "#7f1d1d",
      "#450a0a",
    ],
    info: [
      "#f0f9ff",
      "#e0f2fe",
      "#bae6fd",
      "#7dd3fc",
      "#38bdf8",
      "#0ea5e9", // ⬅️ clean blue
      "#0284c7",
      "#0369a1",
      "#075985",
      "#0c4a6e",
    ],
  },

  headings: {
    fontFamily: `"Segoe UI", "Inter", -apple-system, BlinkMacSystemFont, "Roboto", "Helvetica Neue", Arial, sans-serif`,
    fontWeight: "500", // Modern medium weight
    sizes: {
      h1: {
        fontSize: rem(32),
        lineHeight: "1.2",
        fontWeight: "600",
      },
      h2: {
        fontSize: rem(24),
        lineHeight: "1.25",
        fontWeight: "600",
      },
      h3: {
        fontSize: rem(20),
        lineHeight: "1.3",
        fontWeight: "600",
      },
      h4: {
        fontSize: rem(16),
        lineHeight: "1.35",
        fontWeight: "500",
      },
      h5: {
        fontSize: rem(14),
        lineHeight: "1.4",
        fontWeight: "500",
      },
      h6: {
        fontSize: rem(13),
        lineHeight: "1.45",
        fontWeight: "500",
      },
    },
  },

  spacing: {
    xs: rem(4),
    sm: rem(8),
    md: rem(16),
    lg: rem(24),
    xl: rem(40),
  },

  // Clean, minimal shadows - style
  shadows: {
    xs: "0 1px 2px 0 rgb(0 0 0 / 0.02)",
    sm: "0 1px 3px 0 rgb(0 0 0 / 0.05), 0 1px 2px -1px rgb(0 0 0 / 0.05)",
    md: "0 4px 6px -1px rgb(0 0 0 / 0.06), 0 2px 4px -2px rgb(0 0 0 / 0.06)",
    lg: "0 10px 15px -3px rgb(0 0 0 / 0.07), 0 4px 6px -4px rgb(0 0 0 / 0.07)",
    xl: "0 20px 25px -5px rgb(0 0 0 / 0.08), 0 8px 10px -6px rgb(0 0 0 / 0.08)",
  },

  // style components
  components: {
    Button: {
      defaultProps: {
        size: "sm",
      },
      styles: {
        root: {
          borderRadius: 0, // Sharp corners
          fontWeight: 500,
          fontSize: rem(13),
          transition: "all 100ms cubic-bezier(0.4, 0, 0.2, 1)",
          border: "1px solid var(--mantine-color-neutral-4)",
          "&:hover": {
            transform: "none",
            backgroundColor: "var(--mantine-color-neutral-2)",
          },
        },
      },
    },

    Card: {
      defaultProps: {
        shadow: "sm",
        radius: 0,
      },
      styles: {
        root: {
          border: "1px solid var(--mantine-color-neutral-3)",
          backgroundColor: "var(--mantine-color-neutral-0)",
          borderRadius: 0,
        },
      },
    },

    Input: {
      styles: {
        input: {
          borderRadius: 0,
          border: "1px solid var(--mantine-color-neutral-4)",
          fontSize: rem(13),
          backgroundColor: "var(--mantine-color-neutral-0)",
          transition: "all 100ms cubic-bezier(0.4, 0, 0.2, 1)",
          "&:focus": {
            borderColor: "var(--mantine-color-slate-6)",
            boxShadow: "inset 0 0 0 1px var(--mantine-color-slate-6)",
          },
        },
      },
    },

    Paper: {
      defaultProps: {
        shadow: "xs",
        radius: 0,
      },
      styles: {
        root: {
          border: "1px solid var(--mantine-color-neutral-3)",
          borderRadius: 0,
        },
      },
    },

    Modal: {
      styles: {
        content: {
          borderRadius: 0,
          border: "1px solid var(--mantine-color-neutral-3)",
        },
        header: {
          borderBottom: "1px solid var(--mantine-color-neutral-3)",
          paddingBottom: rem(16),
          marginBottom: rem(16),
        },
      },
    },

    Divider: {
      styles: {
        root: {
          borderColor: "var(--mantine-color-neutral-3)",
        },
      },
    },

    TextInput: {
      styles: {
        input: {
          borderRadius: 0,
          fontSize: rem(13),
        },
      },
    },

    Select: {
      styles: {
        input: {
          borderRadius: 0,
          fontSize: rem(13),
        },
      },
    },

    Checkbox: {
      styles: {
        input: {
          borderRadius: 0,
        },
      },
    },

    Radio: {
      styles: {
        input: {
          borderRadius: "50%",
        },
      },
    },
  },

  other: {
    borderRadius: 0, // Sharp corners
    transitionSpeed: "100ms", // Quick and snappy
    borderColor: "var(--mantine-color-neutral-3)",
    elevation: {
      subtle: "0 1px 2px rgba(0,0,0,0.02)",
      card: "0 2px 4px rgba(0,0,0,0.05)",
      elevated: "0 4px 8px rgba(0,0,0,0.06)",
      floating: "0 8px 16px rgba(0,0,0,0.08)",
    },
  },
});

// Clean, modern palette for charts and data visualization
export const colors = [
  "#64748b", // slate
  "#22c55e", // green
  "#f59e0b", // amber
  "#dc2626", // red
  "#0ea5e9", // blue
  "#8b5cf6", // purple
  "#06b6d4", // cyan
  "#84cc16", // lime
  "#f97316", // orange
  "#ec4899", // pink
];