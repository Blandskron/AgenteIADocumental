export function AppShell({ sidebarOpen, sidebar, children }) {
  return (
    <div className={`app-shell ${sidebarOpen ? "" : "sidebar-collapsed"}`}>
      {sidebar}
      {children}
    </div>
  );
}
