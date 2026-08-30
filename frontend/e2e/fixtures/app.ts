import { expect, test as base, type APIRequestContext, type Page } from '@playwright/test';

export const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? 'admin@quermed.com';
export const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'e2e-admin-passphrase';
export const API_URL = process.env.E2E_API_URL ?? 'http://localhost:8000';

export function uniqueSuffix(): string {
  return `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`;
}

/** Log in through the real UI and wait for the shell. */
export async function loginAs(page: Page, email: string, password: string): Promise<void> {
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Contraseña').fill(password);
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page.getByRole('heading', { name: /^Hoy/, level: 1 })).toBeVisible();
}

export async function logout(page: Page): Promise<void> {
  await page.goto('/mas');
  await page.getByRole('button', { name: 'Cerrar sesión' }).click();
  await expect(page.getByRole('heading', { name: 'Entrar en Quermed CRM' })).toBeVisible();
}

/** Minimal API client for fixtures (creates data through the public API as the admin). */
export class ApiFixtures {
  private token: string | null = null;

  constructor(private readonly request: APIRequestContext) {}

  private async authenticate(): Promise<string> {
    if (this.token) return this.token;
    const response = await this.request.post(`${API_URL}/api/v1/auth/login`, {
      data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD },
    });
    expect(response.ok(), await response.text()).toBeTruthy();
    const body = (await response.json()) as { access_token: string };
    this.token = body.access_token;
    return this.token;
  }

  async createTerritory(name: string, provinces: string[]): Promise<{ id: string }> {
    const token = await this.authenticate();
    const response = await this.request.post(`${API_URL}/api/v1/territories`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { name, provinces },
    });
    expect(response.status(), await response.text()).toBe(201);
    return (await response.json()) as { id: string };
  }

  /** Provinces not yet claimed by any territory (the DB persists between local runs). */
  async freeProvinces(candidates: string[]): Promise<string[]> {
    const token = await this.authenticate();
    const response = await this.request.get(`${API_URL}/api/v1/territories?page_size=200`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(response.ok(), await response.text()).toBeTruthy();
    const body = (await response.json()) as { items: { provinces: string[] }[] };
    const taken = new Set(body.items.flatMap((territory) => territory.provinces));
    return candidates.filter((code) => !taken.has(code));
  }

  async listDivisions(): Promise<{ id: string; code: string }[]> {
    const token = await this.authenticate();
    const response = await this.request.get(`${API_URL}/api/v1/divisions`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(response.ok(), await response.text()).toBeTruthy();
    return (await response.json()) as { id: string; code: string }[];
  }

  async createUser(input: {
    email: string;
    full_name: string;
    role: string;
    password: string;
    territory_ids?: string[];
    division_ids?: string[];
  }): Promise<{ id: string; version: number; email: string }> {
    const token = await this.authenticate();
    const response = await this.request.post(`${API_URL}/api/v1/users`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { territory_ids: [], division_ids: [], ...input },
    });
    expect(response.status(), await response.text()).toBe(201);
    return (await response.json()) as { id: string; version: number; email: string };
  }

  /** Create a product on the Hadeco brand and the Dopplers family (both seeded). */
  async createProduct(input: {
    sku: string;
    name: string;
    list_price: string;
  }): Promise<{ id: string }> {
    const token = await this.authenticate();
    const bundle = await this.request.get(`${API_URL}/api/v1/reference-data`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(bundle.ok(), await bundle.text()).toBeTruthy();
    const data = (await bundle.json()) as {
      brands: { id: string; code: string }[];
      product_families: { id: string; code: string }[];
    };
    const brand = data.brands.find((b) => b.code === 'hadeco')!;
    const family = data.product_families.find((f) => f.code === 'dopplers')!;
    const response = await this.request.post(`${API_URL}/api/v1/products`, {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        ...input,
        brand_id: brand.id,
        family_id: family.id,
        kind: 'equipment',
      },
    });
    expect(response.status(), await response.text()).toBe(201);
    return (await response.json()) as { id: string };
  }

  async createAccount(input: { name: string; province_code: string }): Promise<{ id: string }> {
    const token = await this.authenticate();
    const bundle = await this.request.get(`${API_URL}/api/v1/reference-data`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(bundle.ok(), await bundle.text()).toBeTruthy();
    const data = (await bundle.json()) as { account_types: { id: string }[] };
    const response = await this.request.post(`${API_URL}/api/v1/accounts`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { ...input, account_type_id: data.account_types[0].id },
    });
    expect(response.status(), await response.text()).toBe(201);
    return (await response.json()) as { id: string };
  }

  async createOpportunity(input: {
    account_id: string;
    division_id: string;
    estimated_amount: string;
    owner_id: string;
    name: string;
  }): Promise<{ id: string; version: number }> {
    const token = await this.authenticate();
    const response = await this.request.post(`${API_URL}/api/v1/opportunities`, {
      headers: { Authorization: `Bearer ${token}` },
      data: input,
    });
    expect(response.status(), await response.text()).toBe(201);
    return (await response.json()) as { id: string; version: number };
  }

  async addOpportunityLine(
    opportunityId: string,
    version: number,
    input: { product_id: string; quantity: string },
  ): Promise<void> {
    const token = await this.authenticate();
    const response = await this.request.post(
      `${API_URL}/api/v1/opportunities/${opportunityId}/lines`,
      {
        headers: { Authorization: `Bearer ${token}`, 'If-Match': `"${version}"` },
        data: input,
      },
    );
    expect(response.status(), await response.text()).toBe(201);
  }

  /** Existing territories, for specs that can reuse one when no province is free. */
  async listTerritories(): Promise<{ id: string; provinces: string[] }[]> {
    const token = await this.authenticate();
    const response = await this.request.get(`${API_URL}/api/v1/territories?page_size=200`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(response.ok(), await response.text()).toBeTruthy();
    const body = (await response.json()) as { items: { id: string; provinces: string[] }[] };
    return body.items;
  }

  async createQuote(opportunityId: string): Promise<{ id: string; version: number }> {
    const token = await this.authenticate();
    const response = await this.request.post(`${API_URL}/api/v1/quotes`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { opportunity_id: opportunityId },
    });
    expect(response.status(), await response.text()).toBe(201);
    return (await response.json()) as { id: string; version: number };
  }

  async sendQuoteWithoutEmail(
    quoteId: string,
    version: number,
  ): Promise<{ display_number: string }> {
    const token = await this.authenticate();
    const response = await this.request.post(`${API_URL}/api/v1/quotes/${quoteId}/send`, {
      headers: { Authorization: `Bearer ${token}`, 'If-Match': `"${version}"` },
      data: { skip_email: true },
    });
    expect(response.ok(), await response.text()).toBeTruthy();
    return (await response.json()) as { display_number: string };
  }

  /** The quote PDF endpoint should answer with real PDF bytes. */
  async fetchQuotePdf(quoteId: string): Promise<{ status: number; isPdf: boolean }> {
    const token = await this.authenticate();
    const response = await this.request.get(`${API_URL}/api/v1/quotes/${quoteId}/pdf`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const body = await response.body();
    return {
      status: response.status(),
      isPdf: body.subarray(0, 4).toString('latin1') === '%PDF',
    };
  }

  async deactivateUser(id: string, version: number): Promise<void> {
    const token = await this.authenticate();
    const response = await this.request.patch(`${API_URL}/api/v1/users/${id}`, {
      headers: { Authorization: `Bearer ${token}`, 'If-Match': `"${version}"` },
      data: { is_active: false },
    });
    expect(response.ok(), await response.text()).toBeTruthy();
  }
}

export const test = base.extend<{ api: ApiFixtures }>({
  api: async ({ request }, use) => {
    await use(new ApiFixtures(request));
  },
});

export { expect };
