import { useState } from "react";
export function useSidebarState() {
  return useState(() => !window.matchMedia("(max-width: 760px)").matches);
}
