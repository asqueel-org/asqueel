"""Record exact legacy algorithm bodies across the eight frozen snapshots."""
import ast
import hashlib
import json
from pathlib import Path

base=Path('/tmp/asqueel-formula-baseline')
out=Path('docs/design/evidence/scanner-comparison')
refs=json.loads(Path('docs/design/evidence/hierarchical-select/verification.json').read_text())['legacy_probe']
paths={'compiler':'gnrpy/gnr/sql/gnrsqldata/compiler.py','strings':'gnrpy/gnr/core/gnrstring.py',
       'postgres':'gnrpy/gnr/sql/adapters/gnrpostgres.py','sqlite':'gnrpy/gnr/sql/adapters/gnrsqlite.py',
       'execute':'gnrpy/gnr/sql/gnrsql/execute.py'}
names={'updateFieldDict','embedFieldPars','templateReplace','prepareSqlText','execute'}
result={}
for ref in refs:
    result[ref]={'commit':refs[ref]['commit'],'methods':{}}
    for area,path in paths.items():
        if area=='execute' and not (base/ref/path).exists():
            path='gnrpy/gnr/sql/gnrsql.py'
        parsed=ast.parse((base/ref/path).read_text())
        for node in ast.walk(parsed):
            if not isinstance(node,ast.FunctionDef) or node.name not in names:
                continue
            if node.name=='execute' and area!='execute':
                continue
            first=node.body[0]
            if isinstance(first,ast.Expr) and isinstance(first.value,ast.Constant) and isinstance(first.value.value,str):
                node.body=node.body[1:]
            result[ref]['methods'][area+'.'+node.name]={'path':path,'line':node.lineno,
                'ast_sha256_without_docstring':hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()}
(out/'legacy-algorithms.json').write_text(json.dumps(result,indent=2)+'\n')
for key,value in result['legacy']['methods'].items():
    same=[ref for ref,data in result.items() if data['methods'].get(key,{}).get('ast_sha256_without_docstring')==value['ast_sha256_without_docstring']]
    print(key,'identical AST',len(same),'of',len(refs),','.join(same))
