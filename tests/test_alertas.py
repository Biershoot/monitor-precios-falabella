import pandas as pd
import pytest

from monitor_precios import __main__ as cli
from monitor_precios import analisis


def historial(*precios):
    return pd.DataFrame({"fecha": [f"2026-11-{9 + 7 * i:02d}" for i in range(len(precios))],
                         "precio_articulo": list(precios)})


@pytest.mark.parametrize("datos", [None, historial(59900), historial(59900, 59900)])
def test_sin_cambio(datos):
    assert analisis.cambio_precio(datos) is None


def test_bajada_de_precio():
    cambio = analisis.cambio_precio(historial(59900, 59900, 49900))
    assert cambio == {"fecha_anterior": "2026-11-16", "precio_anterior": 59900,
                      "fecha": "2026-11-23", "precio": 49900, "variacion_pct": -16.7}


def _preparar(tmp_path, monkeypatch, *precios):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "datos").mkdir()
    historial(*precios).to_csv(tmp_path / "datos" / "historial.csv", index=False)
    salida = tmp_path / "salida.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(salida))
    return salida


def test_comando_alerta_con_cambio(tmp_path, monkeypatch, capsys):
    salida = _preparar(tmp_path, monkeypatch, 59900, 64900)
    assert cli.main(["alerta"]) == 0
    assert "subió de $59.900" in capsys.readouterr().out
    texto = salida.read_text(encoding="utf-8")
    assert "cambio=true" in texto
    assert "mensaje=El precio de los Redmi Buds 6 Play subió" in texto


def test_comando_alerta_sin_cambio(tmp_path, monkeypatch):
    salida = _preparar(tmp_path, monkeypatch, 59900, 59900)
    assert cli.main(["alerta"]) == 0
    assert "cambio=false" in salida.read_text(encoding="utf-8")


def test_comando_alerta_fuera_de_github(tmp_path, monkeypatch, capsys):
    _preparar(tmp_path, monkeypatch, 59900, 59900)
    monkeypatch.delenv("GITHUB_OUTPUT")
    assert cli.main(["alerta"]) == 0
    assert "no cambió" in capsys.readouterr().out
