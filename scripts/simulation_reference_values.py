"""Reference values for tests/test_simulation.py, computed independently with SciPy/NumPy.

SciPy and NumPy are used HERE ONLY, to produce the literals pasted into the tests. The
library itself is stdlib-only. Run: python scripts/simulation_reference_values.py
"""
import numpy as np
from scipy import stats

def tri(a, c, b):
    d = stats.triang(c=(c - a) / (b - a), loc=a, scale=b - a)
    return d
def pert(a, m, b, lam=4.0):
    al = 1 + lam * (m - a) / (b - a); be = 1 + lam * (b - m) / (b - a)
    return stats.beta(al, be, loc=a, scale=b - a)
def lognorm_from(mean, sd):
    s2 = np.log(1 + (sd / mean) ** 2); mu = np.log(mean) - s2 / 2
    return stats.lognorm(s=np.sqrt(s2), scale=np.exp(mu)), mu, np.sqrt(s2)

cases = {
    "Uniform(2,10)": stats.uniform(2, 8),
    "Triangular(10,12,20)": tri(10, 12, 20),
    "Triangular(0,9,10)": tri(0, 9, 10),
    "PERT(10,12,20)": pert(10, 12, 20),
    "PERT(0,1,10)": pert(0, 1, 10),
    "Normal(100,15)": stats.norm(100, 15),
    "LogNormal(50,20)": lognorm_from(50, 20)[0],
}
for k, d in cases.items():
    print(k, "mean=%.10f var=%.10f" % (d.mean(), d.var()),
          "P10=%.10f P50=%.10f P90=%.10f" % tuple(d.ppf([.1, .5, .9])))
d, mu, s = lognorm_from(50, 20); print("LogNormal(50,20) mu=%.10f sigma=%.10f" % (mu, s))
print("cdf checks")
for k, x in [("Triangular(10,12,20)", 15.0), ("PERT(10,12,20)", 13.0), ("Normal(100,15)", 110.0), ("LogNormal(50,20)", 60.0), ("Uniform(2,10)", 3.0)]:
    print(k, x, "%.12f" % cases[k].cdf(x))
print("percentile (numpy default linear)")
for arr in ([5.0], [1.0, 2.0], [3, 1, 2, 2, 9, 7, 7, 4], list(range(1, 12))):
    print(arr, [round(float(np.percentile(arr, p)), 12) for p in (0, 10, 25, 50, 90, 100)])
print("truncated normal")
for mu, sd, lo, hi in [(100, 15, 90, 130), (100, 15, None, 110), (100, 15, 95, None)]:
    a = -np.inf if lo is None else (lo - mu) / sd; b = np.inf if hi is None else (hi - mu) / sd
    d = stats.truncnorm(a, b, loc=mu, scale=sd)
    print((mu, sd, lo, hi), "mean=%.10f var=%.10f" % (d.mean(), d.var()),
          "P10=%.10f P50=%.10f P90=%.10f" % tuple(d.ppf([.1, .5, .9])), "cdf(100)=%.12f" % d.cdf(100))
