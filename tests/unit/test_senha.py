import pytest
from funcao import validar_senha

def test_validar_senha_minusculo():
    assert validar_senha("@ph301208") == True

def test_validar_senha_correta():
    assert validar_senha("@Ph301208") == True

