# normalize_rtis.py
import os, unicodedata
folder = "rtis"
for fname in os.listdir(folder):
    if not fname.endswith(".txt"): continue
    p = os.path.join(folder,fname)
    txt = open(p, 'r', encoding='utf-8', errors='replace').read()
    s = unicodedata.normalize("NFKC", txt)
    s = s.replace("\u200c","").replace("\u200d","").replace("\ufeff","")
    s = s.replace("\r\n","\n").replace("\r","\n")
    s = s.replace("“",'\"').replace("”",'\"').replace("’","'").replace("‘","'")
    s = s.replace("—","-").replace("–","-")
    open(p, 'w', encoding='utf-8').write(s)
print("Normalized all RTI files in 'rtis/'.")
