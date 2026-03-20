package com.sentinel.repository;

import com.sentinel.model.ScalingAction;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface ScalingActionRepository extends JpaRepository<ScalingAction, Long> {
    List<ScalingAction> findTop50ByOrderByTimestampDesc();
}
