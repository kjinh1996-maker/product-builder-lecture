
# Lotto Number Generator

## Overview

This application generates a set of random lottery numbers. It's a simple, single-page web application built with HTML, CSS, and JavaScript.

## Features

*   Generates 6 unique random numbers between 1 and 45.
*   Displays the numbers in a visually appealing way.
*   Responsive design for mobile and desktop.
*   Modern and clean user interface.

## Current Plan

*   **index.html:**
    *   Change the title to "Lotto Number Generator".
    *   Add a main container for the application.
    *   Inside the container, add a title `<h1>`.
    *   Add a custom element `<lotto-numbers></lotto-numbers>` to display the generated numbers.
    *   Add a button to trigger the number generation.
*   **style.css:**
    *   Add styles for the main container, title, button, and the number display area.
    *   Use a modern and clean design with a background gradient, clean font, and box shadows.
    *   Ensure the layout is responsive.
*   **main.js:**
    *   Create a custom element `LottoNumbers` that extends `HTMLElement`.
    *   This element will handle generating and displaying the lottery numbers.
    *   The number generation logic will create 6 unique numbers between 1 and 45.
    *   Add an event listener to the "Generate" button to trigger the number generation.
