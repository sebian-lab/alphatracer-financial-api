# Deployment Issues - Alphatracer Backend API

## Issue #1: Missing JWT Module
**Severity:** Critical  
**Status:** Not Fixed  

### Description
The application fails to start with `ModuleNotFoundError: No module named 'jwt'`

### Root Cause
- `python-jose[cryptography]>=3.3.0` provides PyJWT functionality internally
- The package name is different from the import (`import jwt`)
- Either a version mismatch or missing dependency installation occurred during environment setup

### Solution Options:
1. **Quick Fix**: Install PyJWT directly
   ```bash
   pip install PyJWT
   ```

2. **Proper Fix**: Verify `python-jose[cryptography]` is installed and check its submodules
   ```bash
   python -m pip show python-jose[cryptography]
   python -c "import jose; print(jose.__file__)"  # Check if installed correctly
   ```

3. **Code Fix**: If using `python-jose`, imports should typically be:
   ```python
   from jose import jwt  # Standard for python-jose package
   ```

---

## Issue #2: Alembic Binary Not in PATH
**Severity:** Low (non-blocking)  
**Status:** Workaround Applied  

### Description
The `alembic` command not found error, resolved by using `python -m alembic`.

### Solution
Using Python module invocation instead of CLI binary works correctly.

---

## Issue #3: Scripts Not on PATH
**Severity:** Low (informational)  
**Status:** Documented  

### Description
Scripts like `pyrsa-public-key` and `mako-render` installed to `~/.local/bin/` but not accessible system-wide.

### Solution
Add to `.bashrc` or `.profile`:
```bash
export PATH="$HOME/.local/bin:$PATH"
source ~/.bashrc
```

---

## Deployment Checklist

- [x] Database migrations run successfully
- [ ] Application starts without errors (FAILED - Issue #1)
- [ ] All API endpoints functional (NOT TESTED - server down)
- [ ] Documentation accessible at `/docs` (NOT VERIFIED - server down)
- [ ] Environment variables properly configured

## Next Steps
1. Fix JWT import issue by installing PyJWT or correcting the import statement
2. Restart application and test all API endpoints with curl
3. Verify authentication flow, stock queries, and portfolio operations
