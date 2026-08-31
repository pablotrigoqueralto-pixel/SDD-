import { z } from 'zod';

import { phoneRowSchema } from '@/components/shared/PhoneListEditor';

const optionalText = (max: number) => z.string().trim().max(max);

export const accountSchema = z.object({
  name: z.string().trim().min(1, 'accounts:form.nameRequired').max(200),
  account_type_id: z.string().min(1, 'accounts:form.typeRequired'),
  province_code: z.string().min(1, 'accounts:form.provinceRequired'),
  tax_id: optionalText(20),
  street: optionalText(200),
  postal_code: optionalText(10),
  city: optionalText(100),
  phones: z.array(phoneRowSchema),
  email: optionalText(254),
  website: optionalText(200),
  customer_code: optionalText(50),
  notes: optionalText(4000),
  billing_notes: optionalText(4000),
  division_ids: z.array(z.string()),
  brand_ids: z.array(z.string()),
  is_active: z.boolean(),
});

export type AccountInput = z.infer<typeof accountSchema>;

export const addressSchema = z.object({
  label: z.string().trim().min(1, 'accounts:addresses.labelRequired').max(60),
  street: z.string().trim().min(1, 'accounts:addresses.streetRequired').max(200),
  postal_code: z
    .string()
    .trim()
    .regex(/^\d{5}$/, 'accounts:addresses.postalCodeInvalid'),
  city: z.string().trim().min(1, 'accounts:addresses.cityRequired').max(100),
  province_code: z.string().min(1, 'accounts:addresses.provinceRequired'),
  notes: optionalText(500),
});

export const addressesSchema = z.object({
  addresses: z
    .array(addressSchema)
    .max(10, 'accounts:addresses.max')
    .superRefine((addresses, context) => {
      const seen = new Set<string>();
      addresses.forEach((address, index) => {
        const key = address.label.trim().toLocaleLowerCase();
        if (seen.has(key)) {
          context.addIssue({
            code: z.ZodIssueCode.custom,
            path: [index, 'label'],
            message: 'accounts:addresses.labelDuplicated',
          });
        }
        seen.add(key);
      });
    }),
});

export type AddressesInput = z.infer<typeof addressesSchema>;

export const assignmentSchema = z.object({
  owner_id: z.string(),
  territory_id: z.string(),
});

export type AssignmentInput = z.infer<typeof assignmentSchema>;
