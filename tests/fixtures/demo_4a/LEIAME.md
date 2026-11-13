# Fixtures DEMO-4A: dados 100% fictícios

Empresas, postos, produtos, preços e quantidades são inventados para testes. Não representam nenhuma operação real. Contrato: `docs/CONTRATOS_DADOS.md`, seção "Pipeline DEMO-4A". Período de teste: 2026-10-01 a 2026-10-31.

Este arquivo registra a **intenção do desenho** (o que cada linha deveria provocar). O gabarito oficial dos testes é `gabarito.json`, calculado de forma independente a partir das fontes e do contrato, e conciliado com este catálogo.

## vendas.csv (o cabeçalho é a linha 1)
| Linha | id | Intenção |
|---|---|---|
| 2 | V0001 | válida: 40,000 L × 6,199 = 247,96 |
| 3 | V0002 | válida |
| 4 | V0003 | válida, com arredondamento: 30,500 × 4,299 = 131,1195, que vira 131,12 |
| 5 | V0004 | válida (primeira cópia) |
| 6 | V0004 | duplicata exata, descartada |
| 7–8 | V0005 | conflito de ID (quantidades diferentes): ambas em quarentena |
| 9 | V0006 | preço ausente e valor ausente (nunca zero) |
| 10 | V0007 | data inexistente (2026-10-32) |
| 11 | V0008 | produto sem cadastro (ZZ99) |
| 12 | V0009 | unidade fora do cadastro (GAMA) |
| 13 | V0010 | empresa EMP02 com a unidade ALFA (da EMP01) e GC01 ausente no catálogo da EMP02: duas causas |
| 14 | V0011 | quantidade fracionada (1,5) em produto UN |
| 15 | V0012 | quantidade zero |
| 16 | V0013 | quantidade negativa (devoluções não são modeladas) |
| 17 | V0014 | preço negativo |
| 18 | V0015 | preço e valor com vírgula decimal ("3,50") |
| 19 | V0016 | valor informado 10,00, diferente de 2 × 3,50 |
| 20 | V0017 | válida com alerta de produto inativo (CF01) |
| 21 | V0018 | produto com cadastro conflitante (SN01) |
| 22 | V0019 | fora do período (2026-09-30) |
| 23 | V0020 | DS01 existe só na EMP02 (segregação): sem cadastro na EMP01 |
| 24 | V0021 | 23:30 −03:00: competência 2026-10-31, válida |
| 25 | V0022 | 01:30 UTC de 01/11 equivale a 22:30 de 31/10 em São Paulo: válida |
| 26 | V0023 | 03:30 UTC de 01/11 equivale a 00:30 de 01/11 em São Paulo: fora do período |
| 27 | V0024 | empresa vazia |
| 28 | V0025 | coluna a mais (linha malformada) |
| 29 | V0026 | válida, em KG: 0,350 × 39,90 = 13,965, que vira 13,97 |
| 30 | V0027 | válida, código com espaços (" ET01 "), normalização registrada |

## produtos.csv
| Linha | Intenção |
|---|---|
| 2, 3 | válidos (GC01, ET01) |
| 4 / 5 | AG01 válido / duplicata exata descartada |
| 6 | CF01 válido, INATIVO |
| 7–8 | SN01 conflitante (UN × KG): ambos em quarentena |
| 9 | XX01 com unidade CX, fora do domínio |
| 10 | DS01 da EMP02, válido (segregação) |
| 11 | PB01 em KG, válido |
| 12 | LB01 com status SUSPENSO, inválido |

## estoque.csv (foto; sem inferir movimentações)
| Linha | Intenção |
|---|---|
| 2–5 | válidas |
| 6 | duplicata exata da linha 5 |
| 7–8 | conflito de quantidade (BETA, GC01, 31/10) |
| 9 | produto sem cadastro |
| 10 | 2,5 unidades de AG01 (UN) |
| 11 | quantidade negativa |
| 12 | data inexistente (2026-02-30) |
| 13 | quantidade zero (válida) com alerta de produto inativo |
| 14 | válida, em KG |

## Arquivos inválidos
Os testes geram os arquivos inválidos em um diretório temporário: coluna ausente, arquivo vazio e bytes fora de UTF-8. Eles não ficam versionados aqui.
