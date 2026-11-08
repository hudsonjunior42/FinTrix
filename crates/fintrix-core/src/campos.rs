//! Documentos vistos como campos: cada folha do JSON (`contas/c1/nome`) tem um valor e um carimbo.
//! A sincronização mescla campo a campo (vale o carimbo maior); cada gravação carimba a unidade inteira
//! que mudou (o lançamento, ou o registro da configuração: veja `unidade` em lib.rs).
//!
//! Folha = valor que não é objeto, ou objeto vazio. Listas são uma folha só (valem inteiras).
//! O caminho de um campo junta as chaves com `/`, escapando `~` e `/` como no JSON Pointer.

use std::collections::BTreeMap;
use std::time::{SystemTime, UNIX_EPOCH};

use serde_json::{Map, Value};

fn escapar(k: &str) -> String {
    k.replace('~', "~0").replace('/', "~1")
}

fn desescapar(k: &str) -> String {
    k.replace("~1", "/").replace("~0", "~")
}

/// Folhas de um documento: (campo, valor). O documento que não é objeto vira o campo "".
pub fn achatar(doc: &Value) -> BTreeMap<String, Value> {
    fn ir(v: &Value, prefixo: &str, out: &mut BTreeMap<String, Value>) {
        match v {
            Value::Object(m) if !m.is_empty() => {
                for (k, filho) in m {
                    let c = if prefixo.is_empty() { escapar(k) } else { format!("{prefixo}/{}", escapar(k)) };
                    ir(filho, &c, out);
                }
            }
            _ => {
                out.insert(prefixo.to_string(), v.clone());
            }
        }
    }
    let mut out = BTreeMap::new();
    ir(doc, "", &mut out);
    out
}

/// Remonta o documento a partir das folhas vivas (campo → (valor, carimbo)).
/// Se uma folha e outra "dentro" dela estão vivas (mudanças concorrentes: `a` virou número num aparelho e
/// ganhou `a/b` no outro), fica o lado com o carimbo maior. Sem folhas, o documento não existe.
pub fn remontar(folhas: &BTreeMap<String, (Value, String)>) -> Option<Value> {
    if folhas.is_empty() {
        return None;
    }
    let ancestrais = |c: &str| -> Vec<String> {
        let partes: Vec<&str> = if c.is_empty() { vec![] } else { c.split('/').collect() };
        let mut out = vec![String::new()];
        for i in 1..partes.len() {
            out.push(partes[..i].join("/"));
        }
        if c.is_empty() { vec![] } else { out }
    };
    // carimbo mais novo de cada subárvore, para decidir os conflitos folha × descendente
    let mut mais_novo: BTreeMap<String, &str> = BTreeMap::new();
    for (c, (_, h)) in folhas {
        for a in ancestrais(c) {
            let e = mais_novo.entry(a).or_insert(h.as_str());
            if h.as_str() > *e {
                *e = h.as_str();
            }
        }
    }
    let mut raiz = Value::Object(Map::new());
    for (c, (v, h)) in folhas {
        // descartada se um ancestral é folha viva mais nova, ou se ela é ancestral de algo mais novo
        let vencida_por_ancestral = ancestrais(c).iter().any(|a| folhas.get(a).is_some_and(|(_, ha)| ha > h));
        let vencida_por_descendente = mais_novo.get(c).is_some_and(|hd| *hd > h.as_str());
        if vencida_por_ancestral || vencida_por_descendente {
            continue;
        }
        if c.is_empty() {
            raiz = v.clone();
            continue;
        }
        let partes: Vec<String> = c.split('/').map(desescapar).collect();
        inserir(&mut raiz, &partes, v.clone());
    }
    Some(raiz)
}

fn inserir(alvo: &mut Value, partes: &[String], v: Value) {
    if !alvo.is_object() {
        *alvo = Value::Object(Map::new());
    }
    let m = alvo.as_object_mut().unwrap();
    match partes {
        [ultima] => {
            m.insert(ultima.clone(), v);
        }
        [primeira, resto @ ..] => inserir(m.entry(primeira.clone()).or_insert_with(|| Value::Object(Map::new())), resto, v),
        [] => {}
    }
}

/// Relógio lógico híbrido: hora do sistema em ms mais um contador, e o aparelho como desempate.
/// O carimbo é texto que se compara na ordem certa: `0001730000000000-000003-<aparelho>`.
#[derive(Debug, Clone, Default)]
pub struct Relogio {
    ms: u64,
    n: u32,
}

pub fn agora_ms() -> u64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_millis() as u64).unwrap_or(0)
}

pub fn carimbo(ms: u64, n: u32, aparelho: &str) -> String {
    format!("{ms:016}-{n:06}-{aparelho}")
}

/// (ms, contador) de um carimbo; None se o texto não é um carimbo.
pub fn ler_carimbo(c: &str) -> Option<(u64, u32)> {
    let mut p = c.splitn(3, '-');
    Some((p.next()?.parse().ok()?, p.next()?.parse().ok()?))
}

impl Relogio {
    pub fn novo(&mut self, aparelho: &str) -> String {
        let t = agora_ms();
        if t > self.ms {
            self.ms = t;
            self.n = 0;
        } else {
            self.n += 1;
        }
        carimbo(self.ms, self.n, aparelho)
    }

    /// Depois de ver um carimbo de outro aparelho, os próximos daqui são maiores que ele.
    pub fn observar(&mut self, c: &str) {
        if let Some((ms, n)) = ler_carimbo(c) {
            if (ms, n) > (self.ms, self.n) {
                self.ms = ms;
                self.n = n;
            }
        }
    }
}

#[cfg(test)]
mod testes {
    use super::*;
    use serde_json::json;

    fn vivas(pares: &[(&str, Value, &str)]) -> BTreeMap<String, (Value, String)> {
        pares.iter().map(|(c, v, h)| (c.to_string(), (v.clone(), h.to_string()))).collect()
    }

    #[test]
    fn achatar_e_remontar_voltam_ao_mesmo() {
        let doc = json!({"contas": {"c1": {"nome": "Nubank", "inicial": 150000}, "c/2": {}}, "anos": ["2026"], "vazio": {}});
        let f = achatar(&doc);
        assert_eq!(f.get("contas/c1/nome"), Some(&json!("Nubank")));
        assert!(f.contains_key("contas/c~12"));
        assert_eq!(f.get("anos"), Some(&json!(["2026"])));
        let comh: BTreeMap<_, _> = f.into_iter().map(|(c, v)| (c, (v, "1".to_string()))).collect();
        assert_eq!(remontar(&comh), Some(doc));
        assert_eq!(remontar(&BTreeMap::new()), None);
        assert_eq!(remontar(&vivas(&[("", json!(5), "1")])), Some(json!(5)));
    }

    #[test]
    fn conflito_folha_e_descendente_fica_o_mais_novo() {
        let a = vivas(&[("x", json!(1), "2"), ("x/y", json!(2), "1")]);
        assert_eq!(remontar(&a), Some(json!({"x": 1})));
        let b = vivas(&[("x", json!(1), "1"), ("x/y", json!(2), "2")]);
        assert_eq!(remontar(&b), Some(json!({"x": {"y": 2}})));
    }

    #[test]
    fn relogio_avanca_e_observa() {
        let mut r = Relogio::default();
        let a = r.novo("a");
        let b = r.novo("a");
        assert!(b > a);
        let futuro = carimbo(agora_ms() + 60_000, 7, "b");
        r.observar(&futuro);
        assert!(r.novo("a") > futuro);
        assert_eq!(ler_carimbo("0000000000000005-000002-x"), Some((5, 2)));
    }
}
