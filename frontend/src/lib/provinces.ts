/** Spanish provinces (INE codes) grouped by autonomous community. Mirrors the backend list. */

export interface Province {
  code: string;
  name: string;
  community: string;
}

export const PROVINCES: readonly Province[] = [
  { code: '01', name: 'Álava', community: 'País Vasco' },
  { code: '02', name: 'Albacete', community: 'Castilla-La Mancha' },
  { code: '03', name: 'Alicante', community: 'Comunidad Valenciana' },
  { code: '04', name: 'Almería', community: 'Andalucía' },
  { code: '05', name: 'Ávila', community: 'Castilla y León' },
  { code: '06', name: 'Badajoz', community: 'Extremadura' },
  { code: '07', name: 'Illes Balears', community: 'Illes Balears' },
  { code: '08', name: 'Barcelona', community: 'Cataluña' },
  { code: '09', name: 'Burgos', community: 'Castilla y León' },
  { code: '10', name: 'Cáceres', community: 'Extremadura' },
  { code: '11', name: 'Cádiz', community: 'Andalucía' },
  { code: '12', name: 'Castellón', community: 'Comunidad Valenciana' },
  { code: '13', name: 'Ciudad Real', community: 'Castilla-La Mancha' },
  { code: '14', name: 'Córdoba', community: 'Andalucía' },
  { code: '15', name: 'A Coruña', community: 'Galicia' },
  { code: '16', name: 'Cuenca', community: 'Castilla-La Mancha' },
  { code: '17', name: 'Girona', community: 'Cataluña' },
  { code: '18', name: 'Granada', community: 'Andalucía' },
  { code: '19', name: 'Guadalajara', community: 'Castilla-La Mancha' },
  { code: '20', name: 'Gipuzkoa', community: 'País Vasco' },
  { code: '21', name: 'Huelva', community: 'Andalucía' },
  { code: '22', name: 'Huesca', community: 'Aragón' },
  { code: '23', name: 'Jaén', community: 'Andalucía' },
  { code: '24', name: 'León', community: 'Castilla y León' },
  { code: '25', name: 'Lleida', community: 'Cataluña' },
  { code: '26', name: 'La Rioja', community: 'La Rioja' },
  { code: '27', name: 'Lugo', community: 'Galicia' },
  { code: '28', name: 'Madrid', community: 'Comunidad de Madrid' },
  { code: '29', name: 'Málaga', community: 'Andalucía' },
  { code: '30', name: 'Murcia', community: 'Región de Murcia' },
  { code: '31', name: 'Navarra', community: 'Comunidad Foral de Navarra' },
  { code: '32', name: 'Ourense', community: 'Galicia' },
  { code: '33', name: 'Asturias', community: 'Principado de Asturias' },
  { code: '34', name: 'Palencia', community: 'Castilla y León' },
  { code: '35', name: 'Las Palmas', community: 'Canarias' },
  { code: '36', name: 'Pontevedra', community: 'Galicia' },
  { code: '37', name: 'Salamanca', community: 'Castilla y León' },
  { code: '38', name: 'Santa Cruz de Tenerife', community: 'Canarias' },
  { code: '39', name: 'Cantabria', community: 'Cantabria' },
  { code: '40', name: 'Segovia', community: 'Castilla y León' },
  { code: '41', name: 'Sevilla', community: 'Andalucía' },
  { code: '42', name: 'Soria', community: 'Castilla y León' },
  { code: '43', name: 'Tarragona', community: 'Cataluña' },
  { code: '44', name: 'Teruel', community: 'Aragón' },
  { code: '45', name: 'Toledo', community: 'Castilla-La Mancha' },
  { code: '46', name: 'Valencia', community: 'Comunidad Valenciana' },
  { code: '47', name: 'Valladolid', community: 'Castilla y León' },
  { code: '48', name: 'Bizkaia', community: 'País Vasco' },
  { code: '49', name: 'Zamora', community: 'Castilla y León' },
  { code: '50', name: 'Zaragoza', community: 'Aragón' },
  { code: '51', name: 'Ceuta', community: 'Ceuta' },
  { code: '52', name: 'Melilla', community: 'Melilla' },
];

export const PROVINCES_BY_CODE: ReadonlyMap<string, Province> = new Map(
  PROVINCES.map((province) => [province.code, province]),
);

export interface CommunityGroup {
  community: string;
  provinces: Province[];
}

/** Communities alphabetically, provinces alphabetically within each. */
export function provincesByCommunity(): CommunityGroup[] {
  const groups = new Map<string, Province[]>();
  for (const province of PROVINCES) {
    const list = groups.get(province.community) ?? [];
    list.push(province);
    groups.set(province.community, list);
  }
  return [...groups.entries()]
    .map(([community, provinces]) => ({
      community,
      provinces: [...provinces].sort((a, b) => a.name.localeCompare(b.name, 'es')),
    }))
    .sort((a, b) => a.community.localeCompare(b.community, 'es'));
}

export function provinceName(code: string): string {
  return PROVINCES_BY_CODE.get(code)?.name ?? code;
}
