import { Embedded } from "@cerbos/embedded-client";
import wasm from "@cerbos/embedded-server/server.wasm?init";

// One embedded PDP for the whole app, constructed at module scope so the bundle
// download starts before the first render needs a decision. It loads the policy
// bundle from the docs-ui ePDP rule on the acme-docs-prod Hub deployment. The
// rule is public, so no credentials belong here, and it polls Hub for updates.
// Decisions made with it only choose what to render: the API re-checks every
// request with the service PDP.
export const cerbos = new Embedded({
  policies: {
    ruleId: "B7XK2M9QPL4R",
    onUpdate: (error) => {
      if (error) console.warn("Cerbos policy bundle update failed", error);
    },
  },
  wasm,
});
