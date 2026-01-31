package com.terraneuron.ops;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class TerraOpsApplication {

    public static void main(String[] args) {
        SpringApplication.run(TerraOpsApplication.class, args);
    }
}
