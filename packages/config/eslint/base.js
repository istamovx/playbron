import js from '@eslint/js';
import prettier from 'eslint-config-prettier';
import tseslint from 'typescript-eslint';

/** Umumiy flat config. Loyiha qoidasi: `any` yo'q, matn literal yo'q. */
export default tseslint.config(
  {
    ignores: ['dist/**', 'node_modules/**', '.turbo/**', 'coverage/**', '**/*.d.ts'],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    rules: {
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_', caughtErrorsIgnorePattern: '^_' },
      ],
      '@typescript-eslint/consistent-type-imports': [
        'error',
        { prefer: 'type-imports', fixStyle: 'inline-type-imports' },
      ],
      'no-console': ['warn', { allow: ['warn', 'error'] }],
      'no-restricted-properties': [
        'error',
        { object: 'Number', property: 'parseFloat', message: 'Pul butun son (bigint) — float yo‘q.' },
        { object: 'Math', property: 'random', message: 'Deterministik bo‘lmagan qiymat — test va seedda alohida util ishlat.' },
      ],
      eqeqeq: ['error', 'smart'],
    },
  },
  prettier,
);
