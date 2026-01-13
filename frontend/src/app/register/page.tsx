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
  Progress,
} from "@mantine/core";
import {
  IconUser,
  IconLock,
  IconUserPlus,
  IconDatabase,
  IconArrowRight,
  IconCheck,
  IconAlertCircle,
} from "@tabler/icons-react";
import { post } from "@/lib/backendRequests";
import { setAuthCookie } from "@/lib/cookies";
import { ApiResponse } from "@/lib/types";
import { DisplayNotification } from "@/components/Notifications/component";

interface FormData {
  username: string;
  password: string;
  password2: string;
}

interface LoginData {
  session_token: string;
}

interface NotificationState {
  message: string;
  statusCode: number;
}

function getPasswordStrength(password: string): number {
  if (!password) return 0;
  let strength = 0;
  if (password.length >= 8) strength++;
  if (password.length >= 12) strength++;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) strength++;
  if (/\d/.test(password)) strength++;
  if (/[^a-zA-Z0-9]/.test(password)) strength++;
  return Math.min(strength, 4);
}

export default function RegisterPage() {
  const [formData, setFormData] = useState<FormData>({
    username: "",
    password: "",
    password2: "",
  });
  const [loading, setLoading] = useState<boolean>(false);
  const [notification, setNotification] = useState<NotificationState | null>(null);

  const handleFormDataChange = <K extends keyof FormData>(
    field: K,
    value: FormData[K],
  ): void => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const validateForm = (): string | null => {
    if (!formData.username) {
      return "Username is required";
    }
    if (formData.username.length < 3) {
      return "Username must be at least 3 characters";
    }
    if (!formData.password) {
      return "Password is required";
    }
    if (formData.password.length < 8) {
      return "Password must be at least 8 characters";
    }
    if (formData.password !== formData.password2) {
      return "Passwords do not match";
    }
    return null;
  };

  const isFormValid = (): boolean => {
    return !!(
      formData.username &&
      formData.password &&
      formData.password2 &&
      !validateForm()
    );
  };

  const handleRegister = async (): Promise<void> => {
    const validationError = validateForm();
    if (validationError) {
      setNotification({ message: validationError, statusCode: 400 });
      return;
    }

    try {
      setLoading(true);
      setNotification(null);

      const response: ApiResponse<LoginData> = await post(
        "users/register",
        {
          username: formData.username,
          password: formData.password,
          password2: formData.password2,
        },
        false,
      );

      if (response.status === 200 && response.data?.session_token) {
        setNotification({ message: response.message || "Registration successful", statusCode: response.status });
        setAuthCookie(response.data.session_token);
        setTimeout(() => {
          window.location.href = "/ui/connected_apps";
        }, 1000);
      } else {
        setNotification({ message: response.message || "Registration failed", statusCode: response.status || 400 });
      }
    } catch (err: any) {
      setNotification({ message: err.message || "An error occurred during registration", statusCode: 500 });
      console.error("Registration error:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (event: React.KeyboardEvent): void => {
    if (event.key === "Enter" && isFormValid()) {
      handleRegister();
    }
  };

  const passwordStrength = getPasswordStrength(formData.password);
  const passwordsMatch = formData.password && formData.password === formData.password2;

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
              Get Started
            </Title>
            <Text
              size="sm"
              c="slate.5"
              style={{
                fontFamily: "var(--mantine-font-family)",
              }}
            >
              Create your account to get started
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
              placeholder="Choose a username"
              required
              size="sm"
              minLength={3}
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

            <Box>
              <PasswordInput
                label="Password"
                placeholder="Create a strong password"
                required
                size="sm"
                minLength={8}
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
              {formData.password && (
                <Box mt="xs">
                  <Progress
                    value={passwordStrength * 25}
                    size="sm"
                    radius={0}
                    color={
                      passwordStrength === 1
                        ? "error"
                        : passwordStrength === 2
                          ? "warning"
                          : passwordStrength === 3
                            ? "info"
                            : "success"
                    }
                    style={{
                      border: "1px solid var(--mantine-color-neutral-3)",
                    }}
                  />
                  <Text size="xs" c="slate.6" mt={4}>
                    {passwordStrength === 1 && "Weak password"}
                    {passwordStrength === 2 && "Fair password"}
                    {passwordStrength === 3 && "Good password"}
                    {passwordStrength === 4 && "Strong password"}
                  </Text>
                </Box>
              )}
            </Box>

            <PasswordInput
              label="Confirm Password"
              placeholder="Re-enter your password"
              required
              size="sm"
              leftSection={
                formData.password && passwordsMatch ? (
                  <IconCheck size={16} color="var(--mantine-color-success-6)" />
                ) : formData.password2 && !passwordsMatch ? (
                  <IconAlertCircle
                    size={16}
                    color="var(--mantine-color-error-6)"
                  />
                ) : (
                  <IconLock size={16} color="var(--mantine-color-slate-5)" />
                )
              }
              value={formData.password2}
              onChange={(event) =>
                handleFormDataChange("password2", event.currentTarget.value)
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
                  border:
                    formData.password2 && !passwordsMatch
                      ? "1px solid var(--mantine-color-error-6)"
                      : "1px solid var(--mantine-color-neutral-4)",
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
              rightSection={<IconUserPlus size={16} />}
              onClick={handleRegister}
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
              Create Account
            </Button>
          </Stack>

          {/* Footer */}
          <Box pt="md" style={{ borderTop: "1px solid var(--mantine-color-neutral-3)" }}>
            <Group justify="center" gap="xs">
              <Text size="sm" c="slate.6">
                Already have an account?
              </Text>
              <Button
                variant="subtle"
                size="xs"
                rightSection={<IconArrowRight size={14} />}
                onClick={() => {
                  window.location.href = "/login";
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
                Sign In
              </Button>
            </Group>
          </Box>
        </Stack>
      </Paper>
    </Flex>
  );
}