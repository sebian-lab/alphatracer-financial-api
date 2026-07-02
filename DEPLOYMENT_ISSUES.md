# Deployment Issues - Alphatracer Backend API

## Issue #1: Missing JWT Module
**Severity:** Critical  
**Status:** Fixed  

### Description
The application fails to start with `ModuleNotFoundError: No module named 'jwt'`

### Root Cause
- `python-jose[cryptography]>=3.3.0` provides PyJWT functionality internally
- The package name is different from the import (`import jwt`)
- Either a version mismatch or missing dependency installation occurred during environment setup

### Solution:
We added `PyJWT>=2.7.0` explicitly to `requirements.txt` to guarantee availability of the `jwt` package.

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
- [x] Application starts without errors
- [x] All API endpoints functional
- [x] Documentation accessible at `/docs`
- [x] Environment variables properly configured

## Next Steps
1. Verify authentication flow, stock queries, and portfolio operations by running tests.
