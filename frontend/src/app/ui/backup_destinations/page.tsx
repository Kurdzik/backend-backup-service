"use client";

import { useState, useEffect } from "react";
import { BackupDestinationsManager } from "@/components/BackupDestination/component";
import { Stack } from "@mantine/core";

export default function BackupDestinations() {

  return (
    <Stack>
      <BackupDestinationsManager/>
    </Stack>
  );
}
