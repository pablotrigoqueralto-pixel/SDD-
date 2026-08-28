import { expect, loginAs, logout, test, uniqueSuffix } from './fixtures/app';
import { expectNoSeriousA11yViolations } from './fixtures/axe';

test.describe('opportunity pipeline', () => {
  test('rep creates, moves, prices and loses an opportunity; manager reopens from the board', async ({
    page,
    api,
  }, testInfo) => {
    const isMobile = testInfo.project.name === 'mobile-chromium';
    const suffix = uniqueSuffix();
    const password = 'opp-e2e-passphrase';
    const parity = isMobile ? 0 : 1;
    const pool = Array.from({ length: 52 }, (_, i) => String(i + 1).padStart(2, '0')).filter(
      (code) => Number(code) % 2 === parity,
    );
    const provinces = await api.freeProvinces(pool);
    const province = provinces[Math.floor(provinces.length / 2)] ?? '';
    expect(province, 'a free province is needed').toBeTruthy();
    const territory = await api.createTerritory(`Opp ${suffix}`, [province]);
    const divisions = await api.listDivisions();
    const vascular = divisions.find((d) => d.code === 'vascular')!;
    const rep = await api.createUser({
      email: `opp-rep-${suffix}@quermed.com`,
      full_name: `Rep ${suffix}`,
      role: 'sales_rep',
      password,
      territory_ids: [territory.id],
      division_ids: [vascular.id],
    });
    const manager = await api.createUser({
      email: `opp-mgr-${suffix}@quermed.com`,
      full_name: `Manager ${suffix}`,
      role: 'sales_manager',
      password,
    });
    const accountName = `Centro Opp ${suffix}`;
    const opportunityName = `Doppler ${suffix}`;

    // Rep creates the centre and an opportunity from its 360º page
    await loginAs(page, rep.email, password);
    await page.goto('/centros/nuevo');
    const accountForm = page.getByRole('dialog');
    await accountForm.getByLabel('Nombre').fill(accountName);
    await accountForm.getByRole('combobox', { name: 'Tipo' }).selectOption({ index: 1 });
    await accountForm.getByRole('combobox', { name: 'Provincia' }).selectOption(province);
    await accountForm.getByRole('button', { name: 'Guardar' }).click();
    await expect(page.getByRole('heading', { name: accountName })).toBeVisible();

    await page.getByRole('button', { name: 'Nueva oportunidad' }).first().click();
    const opportunityForm = page.getByRole('dialog');
    await opportunityForm
      .getByRole('combobox', { name: 'División' })
      .selectOption({ label: 'Vascular' });
    await expect(opportunityForm.getByText('Pipeline: Equipos')).toBeVisible();
    await opportunityForm.getByLabel('Importe estimado').fill('30.000');
    await opportunityForm.getByRole('button', { name: 'Más datos (opcional)' }).click();
    await opportunityForm.getByLabel('Nombre').fill(opportunityName);
    await expectNoSeriousA11yViolations(page);
    await opportunityForm.getByRole('button', { name: 'Guardar' }).click();

    // The sheet opens with the defaults
    await expect(page.getByRole('heading', { name: opportunityName, level: 1 })).toBeVisible();
    await expect(page.getByText('30.000,00 €').first()).toBeVisible();
    await expectNoSeriousA11yViolations(page);

    // Move stage (picker works on both layouts)
    await page.getByRole('combobox', { name: 'Etapa' }).selectOption({ label: 'Demo' });
    await expect(page.getByText('Oportunidad movida a Demo').first()).toBeVisible();

    // Add a product line: the amount recomputes
    const sku = `OPP-${suffix.toUpperCase()}`;
    await api.createProduct({
      sku,
      name: `Doppler producto ${suffix}`,
      list_price: '12500',
    });
    await page.getByRole('searchbox', { name: 'Buscar producto' }).fill(sku);
    const productSelect = page.getByRole('combobox', { name: /Producto/ });
    await expect(productSelect.getByRole('option', { name: new RegExp(sku) })).toBeAttached();
    await productSelect.selectOption({ index: 1 });
    const quantity = page.getByLabel('Cantidad');
    await quantity.fill('2');
    await page.getByRole('button', { name: 'Añadir producto' }).click();
    await expect(page.getByText('25.000,00 €').first()).toBeVisible();

    // Lose it with Competidor: the brand is required
    await page.getByRole('button', { name: 'Perder' }).first().click();
    const loseForm = page.getByRole('dialog');
    await loseForm.getByRole('combobox', { name: 'Motivo' }).selectOption({ label: 'Competidor' });
    await loseForm.getByRole('button', { name: 'Perder' }).click();
    await expect(loseForm.getByText('Indica la marca competidora')).toBeVisible();
    await loseForm
      .getByRole('combobox', { name: 'Marca competidora' })
      .selectOption({ label: 'Hadeco' });
    await loseForm.getByRole('button', { name: 'Perder' }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(page.getByText('Perdida').first()).toBeVisible();

    // The account timeline shows the stage entries
    await page.goto(`/oportunidades`);
    await expect(page.getByRole('heading', { name: 'Pipeline', level: 1 })).toBeVisible();
    await logout(page);

    // Manager: board totals on desktop (list on mobile) and reopen
    await loginAs(page, manager.email, password);
    await page.goto('/oportunidades');
    await expectNoSeriousA11yViolations(page);
    if (!isMobile) {
      await expect(page.getByText(/Ganadas este mes/)).toBeVisible();
    }
    await page.goto(`/oportunidades?status=lost&q=${encodeURIComponent(suffix)}`);
    await page.getByText(opportunityName).first().click();
    await expect(page.getByRole('heading', { name: opportunityName, level: 1 })).toBeVisible();
    await page.getByRole('button', { name: 'Reabrir' }).click();
    const reopenDialog = page.getByRole('dialog');
    await reopenDialog.getByRole('combobox', { name: 'Etapa' }).selectOption({ label: 'Demo' });
    await reopenDialog.getByRole('button', { name: 'Guardar' }).click();
    await expect(page.getByText('Oportunidad reabierta').first()).toBeVisible();

    // Timeline of the centre shows the stage history entries
    await page.goto('/centros');
    await page.getByRole('searchbox', { name: 'Buscar' }).fill(accountName);
    await page.getByText(accountName).first().click();
    await expect(page.getByRole('heading', { name: accountName })).toBeVisible();
    await expect(
      page.getByText(`${opportunityName} → Demo`).locator('visible=true').first(),
    ).toBeVisible();
  });
});
