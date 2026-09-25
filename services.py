# Serviços de integração com APIs externas (Google OAuth, Open-Meteo e OSRM)

import re
from typing import Any

import httpx
import requests

from config import ESTADOS_BRASIL, GOOGLE_CLIENT_ID

# ==============================================================================
# 👤 RESPONSABILIDADE DO ALUNO 1: APIs REST, Autenticação JWT e Geocodificação
# ==============================================================================


def verificar_token_google(client: httpx.Client, token: str) -> dict[str, Any] | None:
    """Valida o token JWT no endpoint oficial 'https://oauth2.googleapis.com/tokeninfo'.

    Verifica se o token foi emitido para o GOOGLE_CLIENT_ID configurado no projeto
    e retorna o payload do usuário (sub, name, email, picture) ou None se for inválido.
    """
    # TODO (Aluno 1): Implementar a validação do token JWT junto à API do Google OAuth2
    pass


def obter_sigla_uf(admin1: str, uf_informada: str = "") -> str:
    """Converte o estado retornado pela API (admin1) para a sigla oficial de 2 letras (ex: 'PI').

    Caso a API retorne um nome completo (ex: 'Piauí'), normaliza para a sigla 'PI'.
    Caso contrário, utiliza a UF informada como fallback se for válida.
    """
    # TODO (Aluno 1): Implementar a conversão e normalização da UF
    pass


def buscar_coordenadas(
    client: httpx.Client, cidade: str, uf: str = ""
) -> tuple[float, float, str]:
    """Consulta o Open-Meteo Geocoding com filtro Brasil (country_codes=BR) e timeout=4.0s.

    Retorna a tupla (latitude, longitude, nome_formatado). Caso a busca falhe,
    aplica fallback seguro retornando (0.0, 0.0, "Cidade - UF").
    """
    # TODO (Aluno 1): Implementar a consulta à API de Geocodificação Open-Meteo com filtro Brasil
    pass


# ==============================================================================
# 👤 RESPONSABILIDADE DO ALUNO 2: Telemetria Climática e Roteamento Rodoviário
# ==============================================================================


def obter_clima(client: httpx.Client, lat: float, lon: float) -> dict[str, str]:
    """Consulta o Open-Meteo Forecast e retorna temperatura (°C), umidade (%) e vento (km/h).

    Caso coordenadas sejam inválidas (0.0, 0.0) ou ocorra timeout (4.0s),
    retorna dicionário de contingência com valores 'N/D'.
    """
    fallback: dict[str, str] = {
        "temperatura": "N/D",
        "umidade": "N/D",
        "vento": "N/D",
        "condicao": "N/D",
        "chuva": "N/D",
    }

    if lat == 0.0 and lon == 0.0:
        return fallback

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
        "hourly": "precipitation_probability",
        "timezone": "auto",
    }

    wmo_descricoes = {
        0: "Céu limpo",
        1: "Principalmente limpo",
        2: "Parcialmente nublado",
        3: "Nublado",
        45: "Nevoeiro",
        48: "Nevoeiro com geada",
        51: "Garoa leve",
        53: "Garoa moderada",
        55: "Garoa densa",
        61: "Chuva fraca",
        63: "Chuva moderada",
        65: "Chuva forte",
        71: "Neve fraca",
        73: "Neve moderada",
        75: "Neve forte",
        80: "Pancadas de chuva leves",
        81: "Pancadas de chuva moderadas",
        82: "Pancadas de chuva violentas",
        95: "Tempestade",
        96: "Tempestade com granizo leve",
        99: "Tempestade com granizo forte",
    }

    try:
        if client is not None:
            resposta = client.get(url, params=params, timeout=4.0)
        else:
            with httpx.Client(timeout=4.0) as default_client:
                resposta = default_client.get(url, params=params)

        if resposta.status_code != 200:
            return fallback

        dados = resposta.json()
        current = dados.get("current", {})
        temp = current.get("temperature_2m")
        umid = current.get("relative_humidity_2m")
        vento = current.get("wind_speed_10m")
        weather_code = current.get("weather_code")

        condicao = wmo_descricoes.get(weather_code, "Tempo estável") if weather_code is not None else "N/D"

        hourly_prob = dados.get("hourly", {}).get("precipitation_probability", [])
        prob_chuva = f"{hourly_prob[0]}%" if hourly_prob and hourly_prob[0] is not None else "0%"

        return {
            "temperatura": f"{temp}°C" if temp is not None else "N/D",
            "umidade": f"{umid}%" if umid is not None else "N/D",
            "vento": f"{vento} km/h" if vento is not None else "N/D",
            "condicao": condicao,
            "chuva": prob_chuva,
        }
    except (requests.RequestException, httpx.HTTPError, KeyError, ValueError, TypeError):
        return fallback


def obter_percurso(
    client: httpx.Client, lat_o: float, lon_o: float, lat_d: float, lon_d: float
) -> dict[str, str]:
    """Consulta o OSRM e calcula distância em km e duração de viagem de carro.

    Em caso de trajetos sem estradas (ex: ilhas) ou timeout (6.0s),
    retorna dicionário com fallback descritivo ('Sem rota direta' / 'Considere voos ou barcos').
    """
    # TODO (Aluno 2): Implementar o cálculo de rota e distância via OSRM com conversão de unidades
    pass
