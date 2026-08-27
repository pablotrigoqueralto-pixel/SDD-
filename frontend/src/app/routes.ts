/** Route constants: Spanish, user-visible path segments; English identifiers in code. */
export const routes = {
  login: '/login',
  today: '/hoy',
  more: '/mas',
  admin: '/admin',
  adminUsers: '/admin/usuarios',
  adminUserNew: '/admin/usuarios/nuevo',
  adminUser: (id: string) => `/admin/usuarios/${id}`,
  adminTerritories: '/admin/territorios',
  adminTerritoryNew: '/admin/territorios/nuevo',
  adminTerritory: (id: string) => `/admin/territorios/${id}`,
} as const;

export function loginWithNext(next: string): string {
  return `${routes.login}?next=${encodeURIComponent(next)}`;
}
