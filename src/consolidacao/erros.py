"""Exceções do pipeline DEMO-4A (contrato em docs/CONTRATOS_DADOS.md)."""


class ErroPipeline(Exception):
    """Base de todos os erros explícitos do pipeline."""


class LoteRejeitado(ErroPipeline):
    """Arquivo ausente, vazio, fora de UTF-8 ou com cabeçalho diferente do contrato."""


class ReconciliacaoFalhou(ErroPipeline):
    """Alguma verificação de reconciliação falhou; nada é publicado."""


class CaminhoNaoPermitido(ErroPipeline):
    """Entrada dentro de <raiz>/data ou saída fora das pastas permitidas."""
