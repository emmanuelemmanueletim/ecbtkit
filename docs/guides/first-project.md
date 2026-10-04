# First Project

## 1. Create a project

```bash
ecbt create my_cbt
cd my_cbt
pip install -r requirements.txt
```

## 2. Start the server

```bash
python main.py
# or
ecbt dev
```

Open http://localhost:8000/docs

## 3. Create an administrator

```bash
ecbt create-admin
```

## 4. Typical workflow via API

1. **Register / Login** → obtain JWT  
2. **Create subjects & topics**  
3. **Create questions** (with options)  
4. **Create an examination** and set selection rules  
5. **Publish** the examination  
6. **Candidate starts** the exam → receives randomized questions  
7. **Submit answers**  
8. **Submit attempt** → receive result  

All examination business logic (timer, randomization, marking, scoring) is handled by eCBTKit.
