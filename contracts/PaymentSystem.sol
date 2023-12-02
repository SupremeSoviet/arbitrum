// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

interface IERC20 {
    function transfer(address recipient, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

contract PaymentSystem {
    address public owner;

    constructor() {
        owner = msg.sender;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can do this");
        _;
    }

    // События
    event PaymentSent(address indexed sender, address indexed receiver, uint amount, address token);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    // Передача прав владельца
    function transferOwnership(address newOwner) public onlyOwner {
        require(newOwner != address(0), "New owner can't be zero-adress");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }

    // Пополнение баланса контракта в ETH
    function depositETH() public payable {}

    // Отправка ETH
    function sendETH(address payable receiver, uint amount) public onlyOwner {
        require(address(this).balance >= amount, "Insufficient balance");
        receiver.transfer(amount);
        emit PaymentSent(msg.sender, receiver, amount, address(0));
    }

    // Отправка токенов ERC-20
    function sendERC20(IERC20 token, address receiver, uint amount) public onlyOwner {
        require(token.balanceOf(address(this)) >= amount, "Number of tokens in contract too low");
        token.transfer(receiver, amount);
        emit PaymentSent(msg.sender, receiver, amount, address(token));
    }

    // Вывод ETH с контракта
    function withdrawETH(uint amount) public onlyOwner {
        payable(msg.sender).transfer(amount);
    }

    // Вывод токенов ERC-20 с контракта
    function withdrawERC20(IERC20 token, uint amount) public onlyOwner {
        token.transfer(msg.sender, amount);
    }

    // Получение баланса ETH контракта
    function getETHBalance() public view returns (uint) {
        return address(this).balance;
    }

    // Получение баланса токенов ERC-20 контракта
    function getERC20Balance(IERC20 token) public view returns (uint) {
        return token.balanceOf(address(this));
    }
}
