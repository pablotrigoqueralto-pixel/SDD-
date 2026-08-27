import js from '@eslint/js';
import queryPlugin from '@tanstack/eslint-plugin-query';
import importPlugin from 'eslint-plugin-import';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import reactPlugin from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  {
    ignores: ['dist', 'coverage', 'playwright-report', 'test-results', 'src/api/schema.d.ts'],
  },
  js.configs.recommended,
  ...tseslint.configs.strictTypeChecked,
  ...tseslint.configs.stylisticTypeChecked,
  jsxA11y.flatConfigs.strict,
  ...queryPlugin.configs['flat/recommended'],
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      react: reactPlugin,
      'react-hooks': reactHooks,
      import: importPlugin,
    },
    settings: { react: { version: 'detect' } },
    rules: {
      ...reactHooks.configs.recommended.rules,
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      '@typescript-eslint/consistent-type-imports': 'error',
      '@typescript-eslint/no-misused-promises': [
        'error',
        { checksVoidReturn: { attributes: false } },
      ],
      '@typescript-eslint/restrict-template-expressions': ['error', { allowNumber: true }],
      'import/order': [
        'error',
        {
          groups: ['builtin', 'external', 'internal', ['parent', 'sibling', 'index']],
          pathGroups: [{ pattern: '@/**', group: 'internal' }],
          pathGroupsExcludedImportTypes: ['builtin'],
          'newlines-between': 'always',
          alphabetize: { order: 'asc', caseInsensitive: true },
        },
      ],
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['@/features/*/*', '!@/features/*/index'],
              message: 'Import features through their index.ts only.',
            },
          ],
        },
      ],
    },
  },
  {
    // User-visible copy must go through t(): literal JSX text is forbidden in UI code.
    files: ['src/features/**/*.tsx', 'src/components/**/*.tsx', 'src/app/**/*.tsx'],
    rules: {
      'react/jsx-no-literals': [
        'error',
        {
          noStrings: true,
          ignoreProps: true,
          allowedStrings: ['·', '—', '/', '(', ')', ':', '%', '€'],
        },
      ],
    },
  },
  {
    // shadcn/ui primitives are vendored code: keep them close to upstream.
    files: ['src/components/ui/**/*.tsx', 'src/hooks/use-toast.ts'],
    rules: {
      'react/jsx-no-literals': 'off',
      '@typescript-eslint/no-confusing-void-expression': 'off',
      '@typescript-eslint/array-type': 'off',
      '@typescript-eslint/no-unused-vars': 'off',
      '@typescript-eslint/no-unnecessary-condition': 'off',
      '@typescript-eslint/no-unnecessary-type-conversion': 'off',
    },
  },
  {
    files: ['**/*.test.{ts,tsx}', 'src/test/**', 'e2e/**'],
    rules: {
      'react/jsx-no-literals': 'off',
      // Playwright's fixture `use` is not a React hook.
      'react-hooks/rules-of-hooks': 'off',
      '@typescript-eslint/no-non-null-assertion': 'off',
      '@typescript-eslint/no-unsafe-assignment': 'off',
    },
  },
  {
    files: ['*.config.{js,ts}', 'postcss.config.js', 'eslint.config.js'],
    ...tseslint.configs.disableTypeChecked,
  },
);
