"""Call counts/timing attribution for the unmodified production pipelines."""
import argparse
import cProfile
import json
from pathlib import Path
import pstats
import sys

from compare_scanners import models, compile_case


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    sys.path.insert(0,'/tmp/asqueel-formula-baseline/legacy/gnrpy')
    sys.path.append('/tmp/asqueel-formula-baseline/env/lib/python3.12/site-packages')
    databases=models('postgresql',include_tree=True)
    result={}
    for size in (1,100):
        case=dict(columns=','.join(f'$amount AS c{i}' for i in range(size)),
                  where='$id=:id',params={'id':1},options={'order_by':'$id'})
        for engine,db in zip(('legacy','current','tree'),databases):
            compile_case(db,engine,case)
            profiler=cProfile.Profile()
            profiler.runcall(compile_case,db,engine,case)
            entries=[]
            for (filename,line,function),(primitive,total,self_time,cumulative,callers) in pstats.Stats(profiler).stats.items():
                if ('/asqueel/' in filename or '/gnr/' in filename) and any(s in filename for s in ('compiler','gnrsqldata','gnrstring','dialect','_compiler_bindings')):
                    entries.append(dict(file=filename,line=line,function=function,calls=total,
                                        self_us=self_time*1e6,cumulative_us=cumulative*1e6))
            result[f'{engine}_{size}']=sorted(entries,key=lambda e:e['cumulative_us'],reverse=True)
    for database in databases[1:]:
        database.close()
    args.out.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    main()
