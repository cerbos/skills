import { defineStore } from "pinia";

export const useUserStore = defineStore("user", {
  state: () => ({ id: null, name: "", roles: [], team: null }),
  actions: {
    async load() {
      Object.assign(this, await fetch("/api/me").then((r) => r.json()));
    },
  },
});
