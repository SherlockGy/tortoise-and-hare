import sys; ts=[float(x) for x in sys.argv[2:]]; out=sys.argv[1]
sys.argv=['x']
from render import *
cols=3; w,h=640,360
sheet=Image.new('RGB',(w*cols,h*((len(ts)+cols-1)//cols)))
for i,T in enumerate(ts):
    im=frame(T).resize((w,h)); ImageDraw.Draw(im).text((8,8),f'{T:.1f}',fill=(255,0,0))
    sheet.paste(im,((i%cols)*w,(i//cols)*h))
sheet.save(out)
