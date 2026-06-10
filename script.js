const question =[
"Explain OOP",
"What is DBMS",
"What is JavaScript?",
"Explain HTML",
"What is CSS?"];
document.getElementById("question").innerText=question;
function checkAnswer(){
    let answer =document.getElementById("answer").value.toLowerCase();
    let score= 0;
    if (answer.includes("encapsulation")) score++;
    if (answer.includes("inheritance")) score++;
    if (answer.includes("polymorphism")) score++;
    if (answer.includes("abstraction")) score++;
    let resultText = "Score: " + score + "/4\n";
    if (score>=3){
        resultText +="Good Answer!"; 
  }
    else{
        resultText += "Try to include key Concepts.";
    }
    document.getElementById("result").innerText=resultText;

}