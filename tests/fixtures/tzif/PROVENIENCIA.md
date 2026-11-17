# Proveniência do arquivo TZif de teste (FASE 4B, R4)

Arquivo usado **somente pelos testes**, por `PYTHONTZPATH` absoluto. Não é dependência do motor e não muda o comportamento de produção: sem base de fusos, o motor continua no fallback UTC−03:00 documentado em `docs/CONTRATOS_DADOS.md`.

| Campo | Valor |
|---|---|
| Arquivo versionado | `tests/fixtures/tzif/America/Sao_Paulo` |
| Formato | TZif versão 2 (cabeçalho `TZif2`), 1430 bytes |
| SHA-256 | `04c06744ee3fe078ef3b8b779e38eb30666bf993e67a092fcaf2fc28f63a64ce` |
| Origem | `C:\Program Files\Git\mingw64\share\zoneinfo\America\Sao_Paulo` (cópia byte a byte, conferida pelo SHA-256 acima) |
| Pacote | `mingw-w64-x86_64-tzdata 2026c-1` (`C:\Program Files\Git\etc\package-versions.txt`) |
| Versão efetiva da base | IANA tz **2026c** (`zoneinfo\tzdata.zi`, primeira linha: `# version 2026c`) |
| Regra de origem | `Z America/Sao_Paulo -3:6:28 - LMT 1914` / `-3 B %z 1963 O 23` / `-3 1 %z 1964` / `-3 B %z` (`tzdata.zi`) |
| Copiado em | 16/11/2026, FASE 4B |

## Condições de redistribuição

Texto integral do arquivo `C:\Program Files\Git\mingw64\share\licenses\tzdata\LICENSE` do mesmo pacote:

> Unless specified below, all files in the tz code and data (including
> this LICENSE file) are in the public domain.
>
> If the files date.c, newstrftime.3, and strftime.c are present, they
> contain material derived from BSD and use the BSD 3-clause license.

O arquivo TZif é dado compilado a partir da base IANA. Ele é de domínio público e não inclui `date.c`, `newstrftime.3` nem `strftime.c`. Por isso pode ser versionado num repositório público.

## Controles

- O `.gitattributes` (`tests/fixtures/** -text`) impede que o Git converta os bytes.
- `tests/test_consolidacao_zoneinfo.py` **falha**, sem pular, se o arquivo faltar ou se o SHA-256 divergir.
- O mesmo teste lê o conteúdo binário de forma independente (com `struct`, sem `zoneinfo`) e confere as transições de 04/11/2018 03:00Z (início do último horário de verão) e de 17/02/2019 02:00Z (fim).

## Atualização

Não substitua o arquivo para fazer um teste passar. Uma nova versão da base IANA exige:

1. novo arquivo com origem e SHA-256 registrados nesta tabela;
2. revisão dos esperados de `test_consolidacao_zoneinfo.py`;
3. registro em `docs/DECISOES.md`.

## Limitação

Os esperados dos testes vêm da mesma base IANA, então não existe um oráculo totalmente independente. As referências normativas usuais são o Decreto nº 9.242/2017, que pôs o início no primeiro domingo de novembro, e o Decreto nº 9.772/2019, que extinguiu o horário de verão. Elas **não foram conferidas na fonte oficial nesta fase**, e a conciliação contra a fonte legal fica pendente.
