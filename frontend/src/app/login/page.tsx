"use client";

import { useState } from "react";
import {
  Title,
  Text,
  Button,
  TextInput,
  PasswordInput,
  Stack,
  Paper,
  Box,
  rem,
  Flex,
  Group,
} from "@mantine/core";
import {
  IconUser,
  IconLock,
  IconLogin,
  IconDatabase,
  IconArrowRight,
} from "@tabler/icons-react";
import { post } from "@/lib/backendRequests";
import { setAuthCookie } from "@/lib/cookies";
import { ApiResponse } from "@/lib/types";
import { DisplayNotification } from "@/components/Notifications/component";

interface FormData {
  username: string;
  password: string;
}

interface LoginData {
  session_token: string;
}

interface NotificationState {
  message: string;
  statusCode: number;
}

interface LoginProps {
  onSwitchToRegister: () => void;
}

export default function Login({ onSwitchToRegister }: LoginProps) {
  const [formData, setFormData] = useState<FormData>({
    username: "",
    password: "",
  });
  const [loading, setLoading] = useState<boolean>(false);
  const [notification, setNotification] = useState<NotificationState | null>(null);

  const handleFormDataChange = <K extends keyof FormData>(
    field: K,
    value: FormData[K],
  ): void => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const isFormValid = (): boolean => {
    return !!(formData.username && formData.password);
  };

  const handleLogin = async (): Promise<void> => {
    if (!isFormValid()) return;

    try {
      setLoading(true);
      setNotification(null);

      const response: ApiResponse<LoginData> = await post(
        "users/login",
        {
          username: formData.username,
          password: formData.password,
        },
        false,
      );

      if (response.status === 200 && response.data?.session_token) {
        setNotification({ message: response.message || "Login successful", statusCode: response.status });
        setAuthCookie(response.data.session_token);
        setTimeout(() => {
          window.location.href = "/ui/connected_apps";
        }, 1000);
      } else {
        setNotification({ message: response.message || "Login failed", statusCode: response.status || 400 });
      }
    } catch (err: any) {
      setNotification({ message: err.message || "An error occurred during login", statusCode: 500 });
      console.error("Login error:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (event: React.KeyboardEvent): void => {
    if (event.key === "Enter" && isFormValid()) {
      handleLogin();
    }
  };

  return (
    <Flex
      justify="center"
      align="center"
      style={{
        minHeight: "100vh",
        width: "100%",
      }}
    >
      <Paper
        shadow="md"
        p="xl"
        radius={0}
        withBorder
        style={{
          width: "100%",
          maxWidth: rem(400),
          backgroundColor: "var(--mantine-color-neutral-0)",
          backdropFilter: "blur(12px)",
          border: "1px solid var(--mantine-color-neutral-2)",
        }}
      >
        <Stack gap="lg">
          {/* Header */}
          <Box ta="center" mb="md">
            <Flex justify="center" mb="md">
              <Box
                style={{
                  padding: rem(12),
                  borderRadius: 0,
                  backgroundColor: "var(--mantine-color-slate-1)",
                  border: "1px solid var(--mantine-color-slate-2)",
                }}
              >
                <IconDatabase
                  size={24}
                  color="var(--mantine-color-slate-6)"
                  stroke={2}
                />
              </Box>
            </Flex>
            <Title
              order={2}
              size="1.5rem"
              fw={600}
              mb="xs"
              c="slate.8"
              style={{
                fontFamily: "var(--mantine-font-family)",
              }}
            >
              Welcome Back
            </Title>
            <Text
              size="sm"
              c="slate.5"
              style={{
                fontFamily: "var(--mantine-font-family)",
              }}
            >
              Sign in to manage your database connections and backups
            </Text>
          </Box>

          {/* Notification */}
          {notification && (
            <DisplayNotification 
              message={notification.message} 
              statusCode={notification.statusCode} 
            />
          )}

          {/* Form */}
          <Stack gap="md">
            <TextInput
              label="Username"
              placeholder="Enter your username"
              required
              size="sm"
              leftSection={
                <IconUser size={16} color="var(--mantine-color-slate-5)" />
              }
              value={formData.username}
              onChange={(event) =>
                handleFormDataChange("username", event.currentTarget.value)
              }
              onKeyPress={handleKeyPress}
              disabled={loading}
              styles={{
                label: {
                  color: "var(--mantine-color-slate-7)",
                  fontSize: rem(13),
                  fontWeight: 500,
                  marginBottom: rem(6),
                },
                input: {
                  fontSize: rem(13),
                  backgroundColor: "var(--mantine-color-neutral-0)",
                  border: "1px solid var(--mantine-color-neutral-4)",
                  borderRadius: 0,
                  "&:focus": {
                    borderColor: "var(--mantine-color-slate-6)",
                    boxShadow: "inset 0 0 0 1px var(--mantine-color-slate-6)",
                  },
                },
              }}
            />

            <PasswordInput
              label="Password"
              placeholder="Enter your password"
              required
              size="sm"
              leftSection={
                <IconLock size={16} color="var(--mantine-color-slate-5)" />
              }
              value={formData.password}
              onChange={(event) =>
                handleFormDataChange("password", event.currentTarget.value)
              }
              onKeyPress={handleKeyPress}
              disabled={loading}
              styles={{
                label: {
                  color: "var(--mantine-color-slate-7)",
                  fontSize: rem(13),
                  fontWeight: 500,
                  marginBottom: rem(6),
                },
                input: {
                  fontSize: rem(13),
                  backgroundColor: "var(--mantine-color-neutral-0)",
                  border: "1px solid var(--mantine-color-neutral-4)",
                  borderRadius: 0,
                  "&:focus": {
                    borderColor: "var(--mantine-color-slate-6)",
                    boxShadow: "inset 0 0 0 1px var(--mantine-color-slate-6)",
                  },
                },
              }}
            />

            <Button
              fullWidth
              size="sm"
              rightSection={<IconLogin size={16} />}
              onClick={handleLogin}
              loading={loading}
              disabled={!isFormValid() || loading}
              mt="md"
              color="slate"
              styles={{
                root: {
                  height: rem(40),
                  fontSize: rem(13),
                  fontWeight: 500,
                  borderRadius: 0,
                  backgroundColor: "var(--mantine-color-slate-6)",
                  transition: "all 100ms cubic-bezier(0.4, 0, 0.2, 1)",
                  "&:hover:not([data-disabled])": {
                    backgroundColor: "var(--mantine-color-slate-7)",
                  },
                  "&[data-disabled]": {
                    backgroundColor: "var(--mantine-color-slate-3)",
                    color: "var(--mantine-color-slate-5)",
                  },
                },
              }}
            >
              Sign In
            </Button>
          </Stack>

          {/* Footer */}
          <Box pt="md" style={{ borderTop: "1px solid var(--mantine-color-neutral-3)" }}>
            <Group justify="center" gap="xs">
              <Text size="sm" c="slate.6">
                Don't have an account?
              </Text>
              <Button
                variant="subtle"
                size="xs"
                rightSection={<IconArrowRight size={14} />}
                onClick={() => {
                  window.location.href = "/register";
                }}
                disabled={loading}
                styles={{
                  root: {
                    color: "var(--mantine-color-slate-6)",
                    fontSize: rem(13),
                    fontWeight: 500,
                    padding: 0,
                    border: 0,
                    height: "auto",
                  },
                }}
              >
                Create Account
              </Button>
            </Group>
          </Box>
        </Stack>
      </Paper>
    </Flex>
  );
}