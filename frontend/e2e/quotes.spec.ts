import { expect, loginAs, test, uniqueSuffix } from './fixtures/app';
import { expectNoSeriousA11yViolations } from './fixtures/axe';

test.describe('quotes', () => {
  test('rep creates a quote from the opportunity, sends it without email, rejects a sibling and accepting wins the opportunity', async ({
    page,
    api,
  }, testInfo) => {
    const isMobile = testInfo.project.name === 'mobile-chromium';
    const suffix = uniqueSuffix();
    const password = 'quo-e2e-passphrase';
    const parity = isMobile ? 0 : 1;
    const pool = Array.from({ length: 52 }, (_, i) => String(i + 1).padStart(2, '0')).filter(
      (code) => Number(code) % 2 === parity,
    );
    // Reuse an existing territory when the local DB has claimed every province.
    const provinces = await api.freeProvinces(pool);
    let province = provinces[Math.floor(provinces.length / 3)] ?? '';
    let territoryId: string;
    if (province) {
      territoryId = (await api.createTerritory(`Quo ${suffix}`, [province])).id;
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
      email: `quo-rep-${suffix}@quermed.com`,
      full_name: `Rep Quo ${suffix}`,
      role: 'sales_rep',
      password,
      territory_ids: [territoryId],
      division_ids: [vascular.id],
    });
    const product = await api.createProduct({
      sku: `QUO-${suffix.toUpperCase()}`,
      name: `Doppler quo ${suffix}`,
      list_price: '12500',
    });
    const account = await api.createAccount({
      name: `Centro Quo ${suffix}`,
      province_code: province,
    });
    const opportunityName = `Quo opp ${suffix}`;
    const opportunity = await api.createOpportunity({
      account_id: account.id,
      division_id: vascular.id,
      estimated_amount: '30000',
      owner_id: rep.id,
      name: opportunityName,
    });
    await api.addOpportunityLine(opportunity.id, opportunity.version, {
      product_id: product.id,
      quantity: '2',
    });

    // Create the quote from the opportunity sheet: lines are copied
    await loginAs(page, rep.email, password);
    await page.goto(`/oportunidades/${opportunity.id}`);
    await expect(page.getByRole('heading', { name: opportunityName, level: 1 })).toBeVisible();
    await page.getByRole('button', { name: 'Nuevo presupuesto' }).click();
    await expect(page.getByRole('heading', { name: /^P-\d{4}-\d{4}/, level: 1 })).toBeVisible();
    const firstQuoteUrl = page.url();
    await expect(page.getByText('Borrador').first()).toBeVisible();
    await expect(page.getByText('25.000,00 €').first()).toBeVisible(); // copied base
    await expect(page.getByText('30.250,00 €').first()).toBeVisible(); // total with 21 % VAT
    await expectNoSeriousA11yViolations(page);

    // Edit the draft: a 10 % discount recomputes the totals live and on save
    await page.getByRole('button', { name: 'Editar' }).click();
    const editForm = page.getByRole('dialog');
    const discount = editForm.getByLabel('Dto. %');
    await discount.fill('10');
    await expect(editForm.getByText('22.500,00 €').first()).toBeVisible();
    await expect(editForm.getByText('27.225,00 €').first()).toBeVisible();
    await expectNoSeriousA11yViolations(page);
    await editForm.getByRole('button', { name: 'Guardar' }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(page.getByText('27.225,00 €').first()).toBeVisible();

    // Send without email: the version freezes and the outbox records the manual path
    await page.getByRole('button', { name: 'Enviar' }).click();
    const sendDialog = page.getByRole('dialog');
    await sendDialog.getByRole('checkbox', { name: /Enviar sin email/ }).check();
    await expectNoSeriousA11yViolations(page);
    await sendDialog.getByRole('button', { name: 'Enviar' }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(page.getByText('Enviado', { exact: true }).first()).toBeVisible();
    await expect(page.getByText(/entrega manual/).first()).toBeVisible();
    await expect(page.getByRole('button', { name: 'Editar' })).toHaveCount(0);

    // The stored PDF is served with real bytes
    const firstQuoteId = firstQuoteUrl.split('/').pop() ?? '';
    const pdf = await api.fetchQuotePdf(firstQuoteId);
    expect(pdf.status).toBe(200);
    expect(pdf.isPdf).toBe(true);

    // A second quote gets rejected with a note
    await page.getByRole('link', { name: opportunityName }).click();
    await expect(page.getByRole('heading', { name: opportunityName, level: 1 })).toBeVisible();
    await page.getByRole('button', { name: 'Nuevo presupuesto' }).click();
    await expect(page.getByRole('heading', { name: /^P-\d{4}-\d{4}/, level: 1 })).toBeVisible();
    await page.getByRole('button', { name: 'Enviar' }).click();
    await page
      .getByRole('dialog')
      .getByRole('checkbox', { name: /Enviar sin email/ })
      .check();
    await page.getByRole('dialog').getByRole('button', { name: 'Enviar' }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await page.getByRole('button', { name: 'Rechazar' }).click();
    const rejectDialog = page.getByRole('dialog');
    await rejectDialog.getByLabel('Motivo (opcional)').fill('Precio alto');
    await rejectDialog.getByRole('button', { name: 'Rechazar presupuesto' }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(page.getByText('Rechazado', { exact: true }).first()).toBeVisible();
    await expect(page.getByText('Precio alto').first()).toBeVisible();

    // Accepting the first quote wins the opportunity with the quote total
    await page.goto(firstQuoteUrl);
    await page.getByRole('button', { name: 'Aceptar', exact: true }).click();
    const acceptDialog = page.getByRole('dialog');
    await expect(acceptDialog.getByText(/Se ganará la oportunidad por 27\.225,00/)).toBeVisible();
    await acceptDialog.getByRole('button', { name: 'Aceptar presupuesto' }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(page.getByText('Aceptado', { exact: true }).first()).toBeVisible();

    await page.getByRole('link', { name: opportunityName }).click();
    await expect(page.getByRole('heading', { name: opportunityName, level: 1 })).toBeVisible();
    await expect(page.getByText('Ganada').first()).toBeVisible();
    await expect(page.getByText('27.225,00 €').first()).toBeVisible();

    // The quotes list shows both current versions with their state
    await page.goto('/presupuestos');
    await expect(page.getByRole('heading', { name: 'Presupuestos', level: 1 })).toBeVisible();
    const rows = page.getByRole('table').or(page.getByRole('list'));
    await expect(rows.getByText('Aceptado', { exact: true }).first()).toBeVisible();
    await expect(rows.getByText('Rechazado', { exact: true }).first()).toBeVisible();
    await expectNoSeriousA11yViolations(page);
  });
});
