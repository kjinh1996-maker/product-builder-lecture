class LottoNumbers extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: 'open' });
        this.numbers = [];
    }

    connectedCallback() {
        this.render();
    }

    generateNumbers() {
        this.numbers = [];
        const min = 1;
        const max = 45;
        while (this.numbers.length < 6) {
            const randomNumber = Math.floor(Math.random() * (max - min + 1)) + min;
            if (!this.numbers.includes(randomNumber)) {
                this.numbers.push(randomNumber);
            }
        }
        this.numbers.sort((a, b) => a - b);
        this.render();
    }

    render() {
        this.shadowRoot.innerHTML = `
            <style>
                :host {
                    display: flex;
                    justify-content: center;
                    gap: 15px;
                    margin: 30px 0;
                }
                .number {
                    width: 60px;
                    height: 60px;
                    background-color: white;
                    color: #333;
                    border-radius: 50%;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    font-size: 1.8rem;
                    font-weight: bold;
                    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
                }
            </style>
        `;
        this.numbers.forEach(number => {
            const numberDiv = document.createElement('div');
            numberDiv.classList.add('number');
            numberDiv.textContent = number;
            this.shadowRoot.appendChild(numberDiv);
        });
    }
}

customElements.define('lotto-numbers', LottoNumbers);

document.getElementById('generate-btn').addEventListener('click', () => {
    document.querySelector('lotto-numbers').generateNumbers();
});
