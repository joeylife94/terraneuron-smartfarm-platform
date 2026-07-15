package com.terraneuron.ops.repository;

import com.terraneuron.ops.entity.CommandOutboxEvent;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

@Repository
public interface CommandOutboxRepository extends JpaRepository<CommandOutboxEvent, Long> {

    Optional<CommandOutboxEvent> findByCommandId(String commandId);

    List<CommandOutboxEvent> findTop50ByStatusAndNextAttemptAtLessThanEqualOrderByCreatedAtAsc(
            CommandOutboxEvent.OutboxStatus status,
            Instant nextAttemptAt);

    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Query("""
            UPDATE CommandOutboxEvent e
               SET e.status = :processing,
                   e.lockedAt = :lockedAt
             WHERE e.id = :id
               AND e.status = :pending
               AND e.nextAttemptAt <= :lockedAt
            """)
    int claimForPublication(
            @Param("id") Long id,
            @Param("pending") CommandOutboxEvent.OutboxStatus pending,
            @Param("processing") CommandOutboxEvent.OutboxStatus processing,
            @Param("lockedAt") Instant lockedAt);

    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Query("""
            UPDATE CommandOutboxEvent e
               SET e.status = :pending,
                   e.lockedAt = NULL,
                   e.nextAttemptAt = :now
             WHERE e.status = :processing
               AND e.lockedAt < :staleBefore
            """)
    int recoverStaleClaims(
            @Param("processing") CommandOutboxEvent.OutboxStatus processing,
            @Param("pending") CommandOutboxEvent.OutboxStatus pending,
            @Param("staleBefore") Instant staleBefore,
            @Param("now") Instant now);
}
