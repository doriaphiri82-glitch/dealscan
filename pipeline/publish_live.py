"""Optional diagnostic cache export, never publication or a live API fallback."""
from __future__ import annotations
import os
from publish import publish_top,read_top


def main() -> int:
    if os.getenv('ENABLE_CACHE_EXPORT')!='true':
        print('Cache export is disabled. Public opportunities come only from verified database rows.')
        return 1
    try:
        if not publish_top() or read_top() is None:
            print('Diagnostic cache update could not be confirmed')
            return 1
    except Exception as exc:
        print(f'Diagnostic cache export failed ({type(exc).__name__})')
        return 1
    print('Verified-only diagnostic cache updated; this did not authorize publication')
    return 0


if __name__=='__main__': raise SystemExit(main())
