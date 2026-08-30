import { expect, loginAs, test, uniqueSuffix } from './fixtures/app';
import { expectNoSeriousA11yViolations } from './fixtures/axe';

test.describe('global search and imports', () => {
  test('back office imports the catalogue with a preview; the rep finds records by accented name and quote number', async ({
    page,
    api,
  }, testInfo) => {
    const isMobile = testInfo.project.name === 'mobile-chromium';
    const suffix = uniqueSuffix();
    const password = 'gsi-e2e-passphrase';
    const parity = isMobile ? 0 : 1;
    const pool = Array.from({ length: 52 }, (_, i) => String(i + 1).padStart(2, '0')).filter(
      (code) => Number(code) % 2 === parity,
    );
    // Reuse an existing territory when the local DB has claimed every province.
    const provinces = await api.freeProvinces(pool);
    let province = provinces[Math.floor(provinces.length / 4)] ?? '';
    let territoryId: string;
    if (province) {
      territoryId = (await api.createTerritory(`Gsi ${suffix}`, [province])).id;
    } else {
      const territories = await api.listTerritories();
      const reusable = territories.find((t) => t.provinces.length > 0);
      expect(reusable, 'an existing territory is needed').toBeTruthy();
      territoryId = reusable!.id;
      province = reusable!.provinces[0]!;
    }
    const divisions = await api.listDivisions();
    const vascular = divisions.find((d) => d.code === 'vascular')!;
    const rep = await api.createUser({
      email: `gsi-rep-${suffix}@quermed.com`,
      full_name: `Rep Gsi ${suffix}`,
      role: 'sales_rep',
      password,
      territory_ids: [territoryId],
      division_ids: [vascular.id],
    });
    const backOffice = await api.createUser({
      email: `gsi-bo-${suffix}@quermed.com`,
      full_name: `BO Gsi ${suffix}`,
      role: 'back_office',
      password,
    });

    const accountName = `Clínica Pérez ${suffix}`;
    const account = await api.createAccount({ name: accountName, province_code: province });
    const opportunityName = `Gsi opp ${suffix}`;
    const opportunity = await api.createOpportunity({
      account_id: account.id,
      division_id: vascular.id,
      estimated_amount: '5000',
      owner_id: rep.id,
      name: opportunityName,
    });
    const quote = await api.createQuote(opportunity.id);
    const sent = await api.sendQuoteWithoutEmail(quote.id, quote.version);

    // Back office: import a small catalogue CSV with a preview and one bad row
    const sku = `GSI-${suffix.toUpperCase()}`;
    const csv =
      'Código;Nombre;Marca;Familia;Tipo;PVP\n' +
      `${sku};Doppler importado ${suffix};Hadeco;Dopplers;equipo;1.250,50\n` +
      `${sku}-B;Marca mala ${suffix};NoExiste;Dopplers;equipo;10\n`;
    await loginAs(page, backOffice.email, password);
    await page.goto('/importar/catalogo');
    await expect(page.getByRole('heading', { name: 'Importar catálogo', level: 1 })).toBeVisible();
    await page
      .locator('input[type="file"]')
      .setInputFiles({ name: 'productos.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) });
    await expect(page.getByRole('heading', { name: 'Vista previa' })).toBeVisible();
    await expect(page.getByText('NoExiste').first()).toBeVisible(); // the error row, first
    await expectNoSeriousA11yViolations(page);
    await page.getByRole('button', { name: 'Importar 1 filas' }).click();
    await expect(page.getByRole('heading', { name: 'Importación completada' })).toBeVisible();
    await expect(page.getByText('1 creado', { exact: true })).toBeVisible();
    await expect(page.getByText('1 error', { exact: true })).toBeVisible();

    // The imported product exists in the catalogue
    await page.goto('/catalogo');
    await page.getByRole('searchbox').first().fill(sku);
    await expect(page.getByText(`Doppler importado ${suffix}`).first()).toBeVisible();
    await page.goto('/mas');
    await page.getByRole('button', { name: 'Cerrar sesión' }).click();
    await expect(page.getByRole('heading', { name: 'Entrar en Quermed CRM' })).toBeVisible();

    // Rep: search by unaccented partial name from the Buscar nav entry
    await loginAs(page, rep.email, password);
    await page.getByRole('link', { name: 'Buscar' }).first().click();
    await expect(page.getByRole('heading', { name: 'Buscar', level: 1 })).toBeVisible();
    const box = page.getByRole('searchbox', { name: 'Buscar' });
    await box.fill(`perez ${suffix}`);
    await expectNoSeriousA11yViolations(page);
    await page.getByRole('button', { name: new RegExp(`^${accountName}`) }).click();
    await expect(page.getByRole('heading', { name: accountName })).toBeVisible();

    // Search the quote number and land on the quote sheet
    await page.getByRole('link', { name: 'Buscar' }).first().click();
    await page.getByRole('searchbox', { name: 'Buscar' }).fill(sent.display_number);
    await page
      .getByRole('button', { name: new RegExp(sent.display_number) })
      .first()
      .click();
    await expect(page.getByRole('heading', { name: sent.display_number, level: 1 })).toBeVisible();

    // Recents remember the visited records on this device
    await page.getByRole('link', { name: 'Buscar' }).first().click();
    await expect(page.getByText('Visitados recientemente')).toBeVisible();
    await expect(
      page.getByRole('button', { name: new RegExp(sent.display_number) }).first(),
    ).toBeVisible();
    await expect(
      page.getByRole('button', { name: new RegExp(`^${accountName}`) }).first(),
    ).toBeVisible();
  });
});
