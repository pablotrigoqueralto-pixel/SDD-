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
  adminBrands: '/admin/marcas',
  adminBrandNew: '/admin/marcas/nueva',
  adminBrand: (id: string) => `/admin/marcas/${id}`,
  adminLossReasons: '/admin/motivos-perdida',
  adminLossReasonNew: '/admin/motivos-perdida/nuevo',
  adminLossReason: (id: string) => `/admin/motivos-perdida/${id}`,
  adminPipelines: '/admin/pipelines',
  adminJobTitles: '/admin/cargos',
  adminJobTitleNew: '/admin/cargos/nuevo',
  adminJobTitle: (id: string) => `/admin/cargos/${id}`,
  accounts: '/centros',
  accountNew: '/centros/nuevo',
  account: (id: string) => `/centros/${id}`,
  accountEdit: (id: string) => `/centros/${id}/editar`,
  accountAssign: (id: string) => `/centros/${id}/asignar`,
  accountAddresses: (id: string) => `/centros/${id}/direcciones`,
  contactNew: (accountId: string) => `/centros/${accountId}/contactos/nuevo`,
  contactEdit: (accountId: string, contactId: string) =>
    `/centros/${accountId}/contactos/${contactId}/editar`,
} as const;

export function loginWithNext(next: string): string {
  return `${routes.login}?next=${encodeURIComponent(next)}`;
}
