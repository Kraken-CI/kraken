import { ComponentFixture, TestBed } from '@angular/core/testing'

import { LogsPanelComponent } from './logs-panel.component'

describe('LogsPanelComponent', () => {
    let component: LogsPanelComponent
    let fixture: ComponentFixture<LogsPanelComponent>

    beforeEach(async () => {
        await TestBed.configureTestingModule({
            declarations: [LogsPanelComponent],
        }).compileComponents()

        fixture = TestBed.createComponent(LogsPanelComponent)
        component = fixture.componentInstance
        fixture.detectChanges()
    })

    it('should create', () => {
        expect(component).toBeTruthy()
    })
})
