// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract EntriTicket {
    struct Ticket {
        address owner;
        string eventId;
        bool isUsed;
    }

    mapping(bytes32 => Ticket) public tickets;

    event TicketIssued(bytes32 ticketId, address owner, string eventId);
    event TicketUsed(bytes32 ticketId);

    function issueTicket(bytes32 ticketId, string memory eventId) public {
        require(tickets[ticketId].owner == address(0), "Ticket already exists");
        tickets[ticketId] = Ticket(msg.sender, eventId, false);
        emit TicketIssued(ticketId, msg.sender, eventId);
    }

    function useTicket(bytes32 ticketId) public {
        require(tickets[ticketId].owner != address(0), "Ticket not found");
        require(!tickets[ticketId].isUsed, "Ticket already used");
        tickets[ticketId].isUsed = true;
        emit TicketUsed(ticketId);
    }

    function getTicket(bytes32 ticketId) public view returns (address, string memory, bool) {
        Ticket memory t = tickets[ticketId];
        return (t.owner, t.eventId, t.isUsed);
    }
}