import { Embedded } from "@cerbos/embedded-client";
import wasm from "@cerbos/embedded-server/server.wasm?init";

export const cerbos = new Embedded({
  policies: {
    ruleId: "B7XK2M9QPL4R",
    credentials: {
      clientId: import.meta.env.VITE_CERBOS_HUB_CLIENT_ID,
      clientSecret: import.meta.env.VITE_CERBOS_HUB_CLIENT_SECRET,
    },
  },
  wasm,
});
