"""Equipe de agentes para evolucao de interface de uma rede social.

Seis agentes nomeados trabalham em rodadas sobre um projeto alvo:

    Caio  - Cacador de Ideias      (referencias: BeReal, Instagram, Letterboxd)
    Vera  - Chefe e Revisora       (define a pauta, aprova ou devolve)
    Iris  - Diretora de Interface  (estrutura, navegacao, hierarquia)
    Theo  - Diretor Visual         (cor, tipografia, espacamento, micro-interacoes)
    Lila  - Bot social, persona ativa
    Rui   - Bot social, persona lurker

Ver README-equipe.md para o desenho completo.
"""

from equipe.config import Config
from equipe.modelos import EstadoDaRodada

__all__ = ["Config", "EstadoDaRodada"]
