# 🥁 app_drum_3.0

O **app_drum_3.0** é a evolução direta do **app_drum_2.0**, trazendo novas funcionalidades que expandem a experiência musical para além da bateria eletrônica. Nesta versão, o aplicativo ganhou recursos de **gravação, loops independentes e integração com instrumentos externos**, permitindo ao usuário criar arranjos mais completos e criativos.

---

## 🚀 Evolução em relação ao app_drum_2.0

No **app_drum_2.0** tínhamos:  
- Sequenciador de bateria com **bumbo, caixa, hi-hat e outros timbres**.  
- Controle de **BPM** com visualização e metrônomo.  
- Presets salvos no **banco de dados (SQLite)** e também exportação em JSON.  
- Importação de músicas para tocar junto e sobrepor grooves da drum machine.  

---

## 🎶 Novas funcionalidades do app_drum_3.0

1. **Gravação de áudio externo (instrumentos)**  
   - Possibilidade de conectar instrumentos (violão, guitarra, teclado, voz via microfone/interface).  
   - Criação de **loops de áudio** diretamente no software.  

2. **Múltiplas camadas de loops independentes**  
   - Gravação de várias pistas (loop 1, loop 2, loop 3…) de forma independente.  
   - Cada pista funciona como uma faixa sobreposta, permitindo **gravações em camadas**.  

3. **Sincronização de tempo automática**  
   - O tempo do **primeiro loop gravado** define a duração padrão.  
   - Todos os próximos loops seguem automaticamente esse tempo, garantindo sincronia.  

4. **Integração Drum Machine + Loops**  
   - Loops gravados funcionam em conjunto com a **drum machine**.  
   - É possível programar a bateria e gravar instrumentos por cima simultaneamente.  

5. **Interface mais fluida para gravação**  
   - Botão de gravação muda de cor durante o processo.  
   - Sem popups ou alertas que interrompam o fluxo criativo.  

---

## 🔜 Próximos desafios

- Mixagem básica dentro do app (controle de volume, pan de cada pista).  
- Exportação final em **.wav ou .mp3** unindo loops e drum machine.  
- Reconhecimento automático de BPM do áudio importado.  

---

## 🛠️ Tecnologias utilizadas

- **Python 3.12**  
- **Tkinter** (Interface gráfica)  
- **Pygame** (áudio e sequenciamento)  
- **Sounddevice** (captura de áudio externo)  
- **SQLite** (armazenamento de presets e grooves)  

---

## 📌 Conclusão

O **app_drum_3.0** marca um salto importante no projeto: de uma **drum machine básica**, evoluímos para um **mini estúdio de criação musical com loops em tempo real**.  
Agora é possível **programar grooves, importar músicas, gravar instrumentos e sobrepor camadas**, criando arranjos completos dentro do app.
