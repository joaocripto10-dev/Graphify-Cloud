---
name: consolidar-dados
description: Planeja uma consolidação de dados e só implementa após aprovação explícita.
disable-model-invocation: true
---

Solicitação: $ARGUMENTS

1. Identifique fontes autorizadas, período, grão, chaves e transformação desejada.
2. Solicite aos agentes `engenheiro-dados`, `qualidade-dados` e `analista-negocios` um contrato e avaliação de riscos.
3. Mostre o plano: arquivos afetados, cópias/rollback, testes de reconciliação e perigos de duplicidade.
4. Antes de escrever código, tocar em dados reais ou instalar pacotes, obtenha autorização explícita para este plano.
5. Se já houver autorização inequívoca na conversa atual para este escopo, implemente em incrementos mínimos; nunca migre produção sem autorização específica.
6. Após implementação, use `auditor-independente` e reporte evidências. Atualize o grafo apenas após mudanças aprovadas.
