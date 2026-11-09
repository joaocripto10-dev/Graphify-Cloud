# Plano inicial de implantação

## Fase 0 — diagnóstico (sem alterações)
- Confirmar VS Code, Claude Code, Git, PowerShell, uv, Graphify e fontes realmente disponíveis.
- Identificar projeto aberto, módulos e estado do Git.
- Verificar quais integrações são locais e quais enviam dados a fornecedores externos.
- Entregar matriz riscos + prioridades para aprovação.

## Fase 1 — grafo
- Registrar Graphify no projeto usando instalador oficial.
- Construir grafo com `/graphify .` após revisar pastas incluídas/excluídas.
- Consultar relações reais entre fontes e módulos.

## Fase 2 — base piloto
- Selecionar uma **amostra sintética/anônima** de vendas ou estoque.
- Definir contrato dos dados e regras de limpeza.
- Produzir pipeline reversível de consolidação com testes de reconciliação.

## Fase 3 — KPIs
- Aprovar fórmulas e granularidade.
- Construir análises com fontes explícitas e cobertura temporal.
- Revisar cálculos com auditor independente.

## Fase 4 — BI e evolução
- Definir formato de painel a partir da necessidade real (não adicionar framework antes).
- Testes funcionais, limites de acesso, atualização e documentação.
- Separar implantação local/produção com autorização específica.
