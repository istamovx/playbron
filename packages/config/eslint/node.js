import globals from 'globals';
import tseslint from 'typescript-eslint';

import base from './base.js';

export default tseslint.config(...base, {
  languageOptions: {
    globals: { ...globals.node },
  },
});
