import time, cryptography
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
sk=Ed25519PrivateKey.generate(); pk=sk.public_key(); m=b"x"*200; s=sk.sign(m)
bad=s[:32]+bytes(32)
for name,sig in (("valid",s),("bad",bad)):
    t=time.perf_counter(); n=0
    while time.perf_counter()-t<1.0:
        try: pk.verify(sig,m)
        except Exception: pass
        n+=1
    print(cryptography.__version__,name,f"{1e6/n:.1f} us")
