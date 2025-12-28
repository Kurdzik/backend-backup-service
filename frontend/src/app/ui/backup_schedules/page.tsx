"use client";

import { useState, useEffect } from "react";
import { BackupScheduleManager } from "@/components/BackupSchedule/component";
import { Stack } from "@mantine/core";

export default function BackupSchedules() {

  return (
    <Stack>
      <BackupScheduleManager/>
    </Stack>
  );
}
