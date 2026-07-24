// MedVault push service worker
self.addEventListener("push", (event) => {
  let data = { title: "MedVault", body: "A redaction job updated." };
  try {
    if (event.data) data = { ...data, ...event.data.json() };
  } catch {
    /* keep defaults */
  }
  const title = data.title || "MedVault";
  const options = {
    body: data.body || "A redaction job reached a terminal state.",
    icon: "/favicon.ico",
    badge: "/favicon.ico",
    tag: data.job_id || "medvault",
    data: { jobId: data.job_id, status: data.status },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const jobId = event.notification.data && event.notification.data.jobId;
  const url = jobId ? `/app/jobs/${jobId}` : "/app";
  event.waitUntil(
    (async () => {
      const clientsArr = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      for (const c of clientsArr) {
        if ("focus" in c) {
          c.navigate(url);
          return c.focus();
        }
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })(),
  );
});
